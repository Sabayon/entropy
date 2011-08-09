# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Graphical Client}.

"""
import threading

from entropy.const import *
from entropy.i18n import _
import entropy.dep
import entropy.tools
from entropy.services.client import WebService
from entropy.misc import ParallelTask

from sulfur.entropyapi import Equo
from sulfur.setup import cleanMarkupString, SulfurConf
from sulfur.core import get_entropy_webservice
from sulfur.event import SulfurSignals


ENTROPY = Equo()
WEBSERV_MAP = {}
UGC_CACHE = {}

def _clear_ugc_cache(*args):
    UGC_CACHE.clear()

SulfurSignals.connect('ugc_data_update', _clear_ugc_cache)
SulfurSignals.connect('ugc_cache_clear', _clear_ugc_cache)

class DummyEntropyPackage:

    def __init__(self, namedesc = None, dummy_type = -1, onlyname = ''):
        self.matched_atom = (0, 0)
        self.installed_match = None
        self.namedesc = namedesc
        self.queued = None
        self.repoid = ''
        self.repoid_clean = ''
        self.name = ''
        self.vote = -1
        self.vote_delayed = -1
        self.color = None
        self.action = None
        self.dbconn = None
        self.masked = None
        self.pkgset = False
        self.is_pkgset_cat = False
        self.broken = False # used by pkgsets
        self.selected_by_user = False
        self.dummy_type = dummy_type
        self.onlyname = onlyname
        self.set_names = set()
        self.set_matches = set()
        self.set_installed_matches = set()
        self.set_from = set()
        self.set_cat_namedesc = None
        self.set_category = False
        self.set_install_incomplete = False
        self.set_remove_incomplete = False
        self.is_downgrade = False
        self.is_group = False

    @property
    def voted(self):
        return 0.0

class EntropyPackage:

    def __init__(self, matched_atom, remote = None, pkgset = None):

        self.pkgset = pkgset
        self.is_pkgset_cat = False
        self.broken = False # used by pkgsets
        self.queued = None
        self.action = None
        self.dummy_type = None
        self.do_purge = False
        self.masked = None
        self.voted = 0.0
        self.color = SulfurConf.color_normal
        self.remote = remote
        self.selected_by_user = False
        self.set_names = set()
        self.set_matches = set()
        self.set_installed_matches = set()
        self.set_from = set()
        self.set_cat_namedesc = None
        self.set_category = False
        self.set_install_incomplete = False
        self.set_remove_incomplete = False
        self.is_downgrade = False
        self.is_group = False
        # might lead to memleaks
        self.__cache = {}

        if self.pkgset:

            # must be available!
            set_match = ENTROPY.Sets().match(matched_atom[1:])
            if not set_match:
                # package set broken
                self.broken = True
                self.set_name = matched_atom
            else:
                (set_from, self.set_name, self.set_matches,) = set_match
                self.set_from.add(set_from)

            self._cat = self.set_name
            self.set_cat_namedesc = self.set_name
            self.matched_repo = self.set_name

            self.matched_id = etpConst['packagesetprefix']
            self.from_installed = False
            self.dbconn = None
            self.dummy_type = -2
            self.is_set_dep = True
            self.set_names = set()
            self.set_category = False

        elif self.remote:

            self.dbconn = ENTROPY.open_temp_repository()
            idpackage = self.dbconn.addPackage(self.remote)
            matched_atom = (idpackage, matched_atom[1])
            self.from_installed = False

        else:

            if matched_atom[1] == 0:
                self.dbconn = ENTROPY.installed_repository()
                self.from_installed = True
            else:
                self.dbconn = ENTROPY.open_repository(matched_atom[1])
                self.from_installed = False

        if isinstance(matched_atom, tuple):
            self.matched_id, self.matched_repo = matched_atom

        self.matched_atom = matched_atom
        self.installed_match = None

    def _get_webservice(self):

        repository_id = self.get_repository_clean()
        webserv = WEBSERV_MAP.get(repository_id)

        if webserv == -1:
            return None # not available
        if webserv is not None:
            return webserv

        try:
            webserv = get_entropy_webservice(ENTROPY, repository_id)
        except WebService.UnsupportedService:
            WEBSERV_MAP[repository_id] = -1
            return None

        WEBSERV_MAP[repository_id] = webserv
        return webserv

    # for debugging purposes, sample method
    """
    def __setattr__(self, name, value):
        if name in ("installed_match", "matched_atom",):
            do_search = True
            try:
                obj_name = str(self)
            except:
                #
                do_search = False
            if do_search:
                if obj_name.find("/flite") != -1:
                    print repr(self), str(self), "=>" , name, ":", value
                    if self.__dict__.get(name) is not None:
                        import pdb; pdb.set_trace()
        self.__dict__[name] = value
    """

    def __del__(self):
        if hasattr(self, 'remote'):
            if self.remote:
                self.dbconn.close()

    def __str__(self):
        if self.pkgset:
            return self.matched_atom
        repo_id = self.repoid_clean
        if repo_id is None:
            repo_id = ''
        return str(self.dbconn.retrieveAtom(self.matched_id)) + \
            etpConst['entropyrevisionprefix'] + \
                str(self.dbconn.retrieveRevision(self.matched_id)) + \
                    etpConst['entropyrepoprefix'] + repo_id

    def __repr__(self):
        return "<EntropyPackage at %s @ %s | a: %s | q: %s brk: %s | ma: %s | im: %s>" % (
            hex(id(self)), str(self), self.action, self.queued, self.broken,
                self.matched_atom, self.installed_match,)

    def __cmp__(self, pkg):
        if pkg.matched_atom == self.matched_atom:
            return 0
        return 1

    def get_pkg(self):
        return self.matched_atom

    def get_tag(self):
        if self.pkgset:
            return ''

        return self.dbconn.retrieveTag(self.matched_id)

    def get_name(self):
        if self.pkgset:
            return self.matched_atom
        cached = self.__cache.get('get_name')
        if cached:
            return cached
        cached = self.dbconn.retrieveAtom(self.matched_id)
        self.__cache['get_name'] = cached
        return cached

    def is_masked(self):

        if self.pkgset:
            return False

        idpackage, idmask = self.dbconn.maskFilter(self.matched_id)
        if idpackage != -1:
            return False
        return True

    def is_user_masked(self):
        if self.from_installed:
            key, slot = self.dbconn.retrieveKeySlot(self.matched_id)
            m_id, m_r = ENTROPY.atom_match(key, match_slot = slot)
            if m_id == -1:
                return False
            return ENTROPY.is_package_masked_by_user((m_id, m_r,))
        return ENTROPY.is_package_masked_by_user(self.matched_atom)

    def is_user_unmasked(self):
        if self.from_installed:
            key, slot = self.dbconn.retrieveKeySlot(self.matched_id)
            m_id, m_r = ENTROPY.atom_match(key, match_slot = slot)
            if m_id == -1:
                return False
            return ENTROPY.is_package_unmasked_by_user((m_id, m_r,))
        return ENTROPY.is_package_unmasked_by_user(self.matched_atom)

    def _get_nameDesc_get_installed_ver(self):
        ver_str = ''
        if not self.installed_match:
            return ver_str

        idpackage = self.installed_match[0]
        if (self.matched_atom[1] == 0) and (self.matched_id == idpackage):
            # there are no updates
            return ver_str

        from_ver = ENTROPY.installed_repository().retrieveVersion(idpackage) or ""
        from_tag = ENTROPY.installed_repository().retrieveTag(idpackage) or ""
        if from_tag:
            from_tag = '#%s' % (from_tag,)

        return from_ver+from_tag

    def get_nameDesc(self):

        if self.pkgset:
            t = self.matched_atom
            desc = _("Recursive Package Set")
            t += '\n<small><span foreground=\'%s\'>%s</span></small>' % (
                SulfurConf.color_pkgdesc, cleanMarkupString(desc),)
            return t

        cached = self.__cache.get('get_nameDesc')
        if cached is not None:
            atom, repo, repo_clean, key, desc, ver_str = cached
        else:
            atom = self.get_name()
            repo = self.get_repository()
            repo_clean = self.get_repository_clean()
            key = entropy.dep.dep_getkey(atom)
            desc = self.get_description(markup = False)
            ver_str = self._get_nameDesc_get_installed_ver()
            self.__cache['get_nameDesc'] = atom, repo, repo_clean, key, desc, \
                ver_str

        if atom is None: # wtf!
            return 'N/A'

        downloads = self.get_ugc_package_downloads()
        ugc_string = '<small>[%s|<span foreground="%s">%s</span>]</small> ' % (
            downloads, SulfurConf.color_title2, repo_clean,)
        if ver_str:
            ver_str = ' <small>{%s: <span foreground="%s">%s</span>}</small>' % (
                _("from"), SulfurConf.color_title2, ver_str,)

        t = '/'.join(atom.split("/")[1:]) + ver_str
        if self.masked:
            t +=  " <small>[<span foreground='%s'>%s</span>]</small>" % (
                SulfurConf.color_title2,
                ENTROPY.Settings()['pkg_masking_reasons'][self.masked],)

        desc = self.get_description(markup = False)
        if not desc:
            desc = _("No description")
        t += '\n' + ugc_string + \
            '<small><span foreground=\'%s\'>%s</span></small>' % (
                SulfurConf.color_pkgdesc, cleanMarkupString(desc),)
        return t

    def get_only_name(self):
        if self.pkgset:
            return self.set_name
        return self.dbconn.retrieveName(self.matched_id)

    def get_repository(self, clean = False):
        if self.pkgset:
            if etpConst['userpackagesetsid'] in self.set_from:
                return _("User")
            return ' '.join([x for x in sorted(self.set_from)])

        if self.matched_atom[1] == 0:
            repoid = self.dbconn.getInstalledPackageRepository(
                self.matched_id)
            if repoid is None:
                if clean:
                    repoid = '--na--'
                else:
                    repoid = _("Not available")
            return repoid
        elif self.matched_repo:
            return self.matched_repo

        if clean:
            return '--na--'
        return _("Not available")

    def get_repository_clean(self):
        return self.get_repository(clean = True)

    def get_idpackage(self):
        return self.matched_id

    def get_revision(self):
        if self.pkgset:
            return 0

        return self.dbconn.retrieveRevision(self.matched_id)

    def is_sys_pkg(self):
        if self.pkgset:
            return False

        cached = self.__cache.get('is_sys_pkg')
        if cached is not None:
            return cached

        match = self.matched_atom
        if (not self.from_installed) and (not self.installed_match):
            return False
        elif self.installed_match:
            match = self.installed_match

        # check if it's a system package
        s = ENTROPY.validate_package_removal(match[0])

        self.__cache['is_sys_pkg'] = not s
        return not s

    def get_install_status(self):
        # 0: from installed db, so it's installed for sure
        # 1: not installed
        # 2: updatable
        # 3: already updated to the latest
        if self.pkgset:
            return 0

        cached = self.__cache.get('get_install_status')
        if cached is not None:
            return cached

        key, slot = self.dbconn.retrieveKeySlot(self.matched_id)
        matches = ENTROPY.installed_repository().searchKeySlot(key, slot)

        if not matches: # not installed, new!
            status = 1
        else:
            rc, matched = ENTROPY.check_package_update(key+":"+slot, deep = True)
            if rc:
                status = 2
            else:
                status = 3

        self.__cache['get_install_status'] = status

    def get_version(self):
        if self.pkgset:
            return "0"

        tag = ""
        vtag = self.dbconn.retrieveTag(self.matched_id)
        if vtag:
            tag = "#"+vtag
        tag += "~"+str(self.dbconn.retrieveRevision(self.matched_id))
        return self.dbconn.retrieveVersion(self.matched_id)+tag

    def get_only_version(self):
        if self.pkgset:
            return "0"
        return self.dbconn.retrieveVersion(self.matched_id)

    def get_download_url(self):
        if self.pkgset:
            return None
        return self.dbconn.retrieveDownloadURL(self.matched_id)

    def get_slot(self):
        if self.pkgset:
            return "0"
        return self.dbconn.retrieveSlot(self.matched_id)

    def get_dependencies(self):
        if self.pkgset:
            return self.set_matches.copy()
        # for now, just return everything but build deps
        # this function is only used in package info window
        return self.dbconn.retrieveDependencies(self.matched_id,
            exclude_deptypes = [etpConst['dependency_type_ids']['bdepend_id']])

    def get_package_metadata(self):
        if self.pkgset:
            return {}
        return self.dbconn.getPackageData(self.matched_id)

    def get_inverse_dependencies(self):
        if self.pkgset:
            return []
        return self.dbconn.retrieveReverseDependencies(self.matched_id,
            atoms = True,
            exclude_deptypes = [etpConst['dependency_type_ids']['bdepend_id']])

    def get_conflicts(self):
        if self.pkgset:
            return []
        return self.dbconn.retrieveConflicts(self.matched_id)

    def get_license(self):
        if self.pkgset:
            return ""
        return self.dbconn.retrieveLicense(self.matched_id)

    def get_changelog(self):
        if self.pkgset:
            return ""
        return self.dbconn.retrieveChangelog(self.matched_id)

    def get_digest(self):
        if self.pkgset:
            return "0"
        return self.dbconn.retrieveDigest(self.matched_id)

    def get_category(self):
        if self.pkgset:
            return self._cat
        cached = self.__cache.get('get_category')
        if cached:
            return cached
        cached = self.dbconn.retrieveCategory(self.matched_id)
        self.__cache['get_category'] = cached
        return cached

    def get_api(self):
        if self.pkgset:
            return "0"
        return self.dbconn.retrieveApi(self.matched_id)

    def get_useflags(self):
        if self.pkgset:
            return []
        return self.dbconn.retrieveUseflags(self.matched_id)

    def get_trigger(self):
        if self.pkgset:
            return ""
        return self.dbconn.retrieveTrigger(self.matched_id)

    def get_config_protect(self):
        if self.pkgset:
            return []
        return self.dbconn.retrieveProtect(self.matched_id)

    def get_config_protect_mask(self):
        if self.pkgset:
            return []
        return self.dbconn.retrieveProtectMask(self.matched_id)

    def get_keywords(self):
        if self.pkgset:
            return []
        return self.dbconn.retrieveKeywords(self.matched_id)

    def get_needed(self):
        if self.pkgset:
            return []
        return self.dbconn.retrieveNeeded(self.matched_id)

    def get_compile_flags(self):
        if self.pkgset:
            return []
        flags = self.dbconn.retrieveCompileFlags(self.matched_id)
        return flags

    def get_sources(self):
        if self.pkgset:
            return []
        return self.dbconn.retrieveSources(self.matched_id)

    def get_homepage(self):
        if self.pkgset:
            return ""
        return self.dbconn.retrieveHomepage(self.matched_id)

    def get_key_slot(self):
        if self.pkgset:
            return self.set_name, "0"
        return self.dbconn.retrieveKeySlot(self.matched_id)

    def get_key(self):
        cached = self.__cache.get('get_key')
        if cached is not None:
            return cached

        if self.pkgset:
            return self.set_name

        key = entropy.dep.dep_getkey(
            self.dbconn.retrieveAtom(self.matched_id))
        self.__cache['get_key'] = key
        return key

    def get_description_no_markup(self):
        if self.pkgset:
            return self.set_cat_namedesc
        return self.get_description(markup = False)

    def get_description(self, markup = True):
        if self.pkgset:
            return self.set_cat_namedesc

        if markup:
            return cleanMarkupString(
                self.dbconn.retrieveDescription(self.matched_id))
        else:
            return self.dbconn.retrieveDescription(self.matched_id)

    def get_download_size(self, debug = False):
        if self.pkgset:
            return 0
        size = self.dbconn.retrieveSize(self.matched_id)
        extra_downloads = self.dbconn.retrieveExtraDownload(self.matched_id)
        for extra_download in extra_downloads:
            if (not debug) and (extra_download['type'] == "debug"):
                continue
            size += extra_download['size']
        return size

    def get_disk_size(self, debug = False):
        if self.pkgset:
            return 0
        size = self.dbconn.retrieveOnDiskSize(self.matched_id)
        extra_downloads = self.dbconn.retrieveExtraDownload(self.matched_id)
        for extra_download in extra_downloads:
            if (not debug) and (extra_download['type'] == "debug"):
                continue
            size += extra_download['disksize']
        return size

    def get_proper_size(self, debug = False):
        if self.from_installed:
            return self.get_disk_sizeFmt(debug = debug)
        else:
            return self.get_download_sizeFmt(debug = debug)

    def get_download_sizeFmt(self, debug = False):
        if self.pkgset:
            return 0
        return entropy.tools.bytes_into_human(self.get_download_size(
            debug = debug))

    def get_disk_sizeFmt(self, debug = False):
        if self.pkgset:
            return 0
        return entropy.tools.bytes_into_human(self.get_disk_size(
            debug = debug))

    def get_arch(self):
        return etpConst['currentarch']

    def get_creation_date(self):
        if self.pkgset:
            return 0
        return self.dbconn.retrieveCreationDate(self.matched_id)

    def get_creation_date_formatted(self):
        if self.pkgset:
            return 0
        return entropy.tools.convert_unix_time_to_human_time(
            float(self.dbconn.retrieveCreationDate(self.matched_id)))

    def get_release(self):
        if self.pkgset:
            return ENTROPY.Settings()['repositories']['branch']
        return self.dbconn.retrieveBranch(self.matched_id)

    def _get_vote_cache(self, pkg_key):
        return UGC_CACHE.get("votes_" + pkg_key)

    def _get_vote_cache_2(self, pkg_key):
        return UGC_CACHE["votes_" + pkg_key]

    def _set_vote_cache(self, pkg_key, val):
        UGC_CACHE["votes_" + pkg_key] = val

    def _get_vote_raw(self, pkg_key):

        cached = self._get_vote_cache(pkg_key)
        if cached == -1:
            return None
        if cached is not None:
            return cached

        webserv = self._get_webservice()
        if webserv is None:
            self._set_vote_cache(pkg_key, -1)
            return None

        # try to get vote for the single package first, if it fails,
        # we'll search the info inside the available vote data.
        try:
            vote = webserv.get_votes([pkg_key], cache = True,
                cached = True)[pkg_key]
        except WebService.CacheMiss:
            vote = None

        # found it?
        if vote is not None:
            self._set_vote_cache(pkg_key, vote)
            return vote
        else:
            self._set_vote_cache(pkg_key, -1)

        # fallback to available cache
        try:
            vote = webserv.get_available_votes(cache = True,
                cached = True).get(pkg_key)
            self._set_vote_cache(pkg_key, vote)
            return vote
        except WebService.CacheMiss:
            self._set_vote_cache(pkg_key, -1)
            return None

    def get_ugc_package_vote_delayed(self):
        if self.pkgset:
            return -1
        atom = self.get_name()
        if not atom:
            return None
        pkg_key = entropy.dep.dep_getkey(atom)
        try:
            vote_raw = self._get_vote_cache_2(pkg_key)
        except KeyError:
            vote_raw = None
            # schedule a new task
            th = ParallelTask(self._get_vote_raw, pkg_key)
            th.start()
        return vote_raw

    def get_ugc_package_vote(self):
        if self.pkgset:
            return -1
        atom = self.get_name()
        if not atom:
            return None
        pkg_key = entropy.dep.dep_getkey(atom)
        return self._get_vote_raw(pkg_key)

    def get_ugc_package_vote_int(self):
        if self.pkgset:
            return 0
        atom = self.get_name()
        if not atom:
            return 0

        pkg_key = entropy.dep.dep_getkey(atom)
        vote = self._get_vote_raw(pkg_key)
        if vote is None:
            return 0
        return int(vote)

    def get_ugc_package_vote_float(self):
        if self.pkgset:
            return 0.0
        atom = self.get_name()
        if not atom:
            return 0.0

        pkg_key = entropy.dep.dep_getkey(atom)
        vote = self._get_vote_raw(pkg_key)
        if vote is None:
            return 0.0
        return vote

    def get_ugc_package_downloads(self):

        if self.pkgset:
            return 0
        atom = self.get_name()
        if not atom:
            return 0

        pkg_key = entropy.dep.dep_getkey(atom)
        cache_key = "downloads_" + pkg_key
        cached = UGC_CACHE.get(cache_key)
        if cached is not None:
            return cached

        webserv = self._get_webservice()
        if webserv is None:
            UGC_CACHE[cache_key] = 0
            return 0
        try:
            downloads = webserv.get_available_downloads(cache = True,
                cached = True).get(pkg_key, 0)
        except WebService.CacheMiss:
            UGC_CACHE[cache_key] = 0
            return 0

        UGC_CACHE[cache_key] = downloads
        return downloads

    def get_attribute(self, attr):
        cached = self.__cache.get(('get_attribute', attr,))

        if cached is not None:
            return cached
        x = None
        if attr == "description":
            x = cleanMarkupString(self.dbconn.retrieveDescription(self.matched_id))
        elif attr == "category":
            x = self.dbconn.retrieveCategory(self.matched_id)
        elif attr == "license":
            x = self.dbconn.retrieveLicense(self.matched_id)
        elif attr == "creationdate":
            x = self.dbconn.retrieveCreationDate(self.matched_id)
        elif attr == "version":
            x = self.dbconn.retrieveVersion(self.matched_id)
        elif attr == "revision":
            x = self.dbconn.retrieveRevision(self.matched_id)
        elif attr == "versiontag":
            x = self.dbconn.retrieveTag(self.matched_id)
            if not x:
                x = "None"
        elif attr == "branch":
            x = self.dbconn.retrieveBranch(self.matched_id)
        elif attr == "name":
            x = self.dbconn.retrieveName(self.matched_id)
        elif attr == "namedesc":
            x = self.get_nameDesc()
        elif attr == "slot":
            x = self.dbconn.retrieveSlot(self.matched_id)

        self.__cache[('get_attribute', attr,)] = x
        return x

    def _get_time( self ):
        if self.pkgset:
            return 0
        return self.dbconn.retrieveCreationDate(self.matched_id)

    def get_filelist( self ):
        if self.pkgset:
            return []
        mycont = sorted(self.dbconn.retrieveContent(self.matched_id))
        return mycont

    def get_filelist_ext( self ):
        if self.pkgset:
            return []
        return self.dbconn.retrieveContent(self.matched_id, extended = True,
            order_by = 'file')

    def get_fullname( self ):
        if self.pkgset:
            return self.set_name
        return self.dbconn.retrieveAtom(self.matched_id)

    @property
    def pkg(self):
        return self.get_pkg()

    @property
    def name(self):
        return self.get_name()

    @property
    def namedesc(self):
        return self.get_nameDesc()

    @property
    def onlyname(self):
        return self.get_only_name()

    @property
    def cat(self):
        return self.get_category()

    @property
    def repoid(self):
        return self.get_repository()

    @property
    def repoid_clean(self):
        return self.get_repository_clean()

    @property
    def ver(self):
        return self.get_version()

    @property
    def binurl(self):
        return self.get_download_url()

    @property
    def onlyver(self):
        return self.get_only_version()

    @property
    def tag(self):
        return self.get_tag()

    @property
    def revision(self):
        return self.get_revision()

    @property
    def digest(self):
        return self.get_digest()

    @property
    def version(self):
        return self.get_version()

    @property
    def release(self):
        return self.get_release()

    @property
    def slot(self):
        return self.get_slot()

    @property
    def maskstat(self):
        return self.is_masked()

    @property
    def keywords(self):
        return self.get_keywords()

    @property
    def useflags(self):
        return self.get_useflags()

    @property
    def homepage(self):
        return self.get_homepage()

    @property
    def protect(self):
        return self.get_config_protect()

    @property
    def protect_mask(self):
        return self.get_config_protect_mask()

    @property
    def trigger(self):
        return self.get_trigger()

    @property
    def compileflags(self):
        return self.get_compile_flags()

    @property
    def dependencies(self):
        return self.get_dependencies()

    @property
    def needed(self):
        return self.get_needed()

    @property
    def conflicts(self):
        return self.get_conflicts()

    @property
    def dependsFmt(self):
        return self.get_inverse_dependencies()

    @property
    def api(self):
        return self.get_api()

    @property
    def content(self):
        return self.get_filelist()

    @property
    def contentExt(self):
        return self.get_filelist_ext()

    @property
    def lic(self):
        return self.get_license()

    @property
    def sources(self):
        return self.get_sources()

    @property
    def keyslot(self):
        return self.get_key_slot()

    @property
    def key(self):
        return self.get_key()

    @property
    def description(self):
        return self.get_description()

    @property
    def description_nomarkup(self):
        return self.get_description_no_markup()

    @property
    def size(self):
        return self.get_download_size(debug = False)

    @property
    def size_debug(self):
        return self.get_download_size(debug = True)

    @property
    def intelligentsizeFmt(self):
        return self.get_proper_size(debug = False)

    @property
    def intelligentsizeDebugFmt(self):
        return self.get_proper_size(debug = True)

    @property
    def sizeFmt(self):
        return self.get_download_sizeFmt(debug = False)

    @property
    def sizeDebugFmt(self):
        return self.get_download_sizeFmt(debug = True)

    @property
    def disksize(self):
        return self.get_disk_size(debug = False)

    @property
    def disksize_debug(self):
        return self.get_disk_size(debug = True)

    @property
    def disksizeFmt(self):
        return self.get_disk_sizeFmt(debug = False)

    @property
    def disksizeDebugFmt(self):
        return self.get_disk_sizeFmt(debug = True)

    @property
    def arch(self):
        return self.get_arch()

    @property
    def epoch(self):
        return self.get_creation_date()

    @property
    def epochFmt(self):
        return self.get_creation_date_formatted()

    @property
    def syspkg(self):
        return self.is_sys_pkg()

    @property
    def install_status(self):
        return self.get_install_status()

    @property
    def vote(self):
        return self.get_ugc_package_vote()

    @property
    def vote_delayed(self):
        return self.get_ugc_package_vote_delayed()

    @property
    def voteint(self):
        return self.get_ugc_package_vote_int()

    @property
    def votefloat(self):
        return self.get_ugc_package_vote_float()

    @property
    def downloads(self):
        return self.get_ugc_package_downloads()

    @property
    def user_unmasked(self):
        return self.is_user_unmasked()

    @property
    def user_masked(self):
        return self.is_user_masked()

    @property
    def changelog(self):
        return self.get_changelog()

    @property
    def pkgmeta(self):
        return self.get_package_metadata()

    @property
    def package_id(self):
        return self.matched_atom[0]

    @property
    def repository_id(self):
        return self.matched_atom[1]
