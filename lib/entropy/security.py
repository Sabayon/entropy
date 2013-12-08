# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework Security module}.

    This module contains Entropy GLSA-based Security interfaces.

"""
import codecs
import datetime
import errno
import os
import shutil
import subprocess
import sys
import time
import hashlib

from entropy.exceptions import EntropyException
from entropy.const import etpConst, const_setup_perms, const_mkdtemp, \
    const_debug_write, const_setup_file, const_setup_directory, \
    const_convert_to_unicode, const_convert_to_rawstring, const_is_python3, \
    const_debug_enabled, const_file_readable
from entropy.i18n import _
from entropy.output import blue, bold, red, darkgreen, darkred, purple, brown
from entropy.cache import EntropyCacher
from entropy.core.settings.base import SystemSettings
from entropy.fetchers import UrlFetcher

import entropy.tools


class System(object):

    """
    ~~ GIVES YOU WINGS ~~

    @note: thanks to Gentoo "gentoolkit" package, License below:
    @note:    This program is licensed under the GPL, version 2

    @note: WARNING: this code is not intended to replace any Security mechanism,
    @note: but it's just a way to handle Gentoo GLSAs.
    @note: There are possible security holes and probably bugs in this code.

    This class implements the Entropy packages Security framework.
    It can be used to retrieve security advisories, get information
    about unapplied advisories, etc.

    For specifications about security advisories metadata format, please see
    docs/metadata/glsa.dtd. Your Source Package Manager must implement
    advisories in this format, with file names ordered by your own criteria,
    which will be matched 1:1 here.
    You should provide a compressed .tar.gz or .tar.bz2 package containing such
    xml files in a way that can be downloaded and installed by this class.
    Your distribution should expose a publicly available URL as well as a valid
    "securityurl" parameter inside repositories.conf.

    To sum up, you as distributor should:
    1. implement your security advisories xml files by looking at
        docs/metadata/glsa.dtd specifications.
    2. setup a cronjob that compresses your unpacked list of advisories
        to a file inside a publicly available URL as well as a valid .md5
        file.
    3. provide a default repositories.conf file with securityurl| pointing
        to that file (HTTP, FTP and FILE protocols supported).
    4. Optionally, in the same dir you could make available a GPG public
        key and a GPG signature of your security advisories .tar.* file.
        The former MUST be named signature.asc while the latter must match
        securityurl value plus ".asc"

    This class uses the Installed Packages Repository but locking is delegated
    to the API user.
    """
    _CACHE_ID = 'advisories_cache_'
    _CACHE_DIR = os.path.join(etpConst['entropyworkdir'], "security_cache")
    SECURITY_DIR = etpConst['securitydir']
    SECURITY_URL = None

    class UpdateError(EntropyException):
        """Raised when security advisories couldn't be updated correctly"""

    def __init__(self, entropy_client):

        """
        Instance constructor.

        @param entropy_client: a valid entropy.client.interfaces.Client
            instance
        @type entropy_client: entropy.client.interfaces.Client instance
        """
        self._entropy = entropy_client
        self.__cacher = None
        self.__settings = None
        self._adv_metadata = None
        self._affected_pkgs = set()
        self._gpg_keystore_dir = os.path.join(etpConst['confdir'],
            "security-advisories-keys")

        self._gpg_feature = True
        env_gpg = os.getenv('ETP_DISABLE_GPG')
        if env_gpg is not None:
            self._gpg_feature = False

        self._op_mappings = {
            "le": "<=",
            "lt": "<",
            "eq": "=",
            "gt": ">",
            "ge": ">=",
            "rge": ">=", # >=~
            "rle": "<=", # <=~
            "rgt": ">", # >~
            "rlt": "<" # <~
        }

        if System.SECURITY_URL is None:
            self._url = \
                self._settings['repositories']['security_advisories_url']
        else:
            self._url = System.SECURITY_URL

    @property
    def _cacher(self):
        """
        Return an EntropyCacher instance, not thread-safe.
        """
        if self.__cacher is None:
            self.__cacher = EntropyCacher()
        return self.__cacher

    @property
    def _settings(self):
        """
        Return a SystemSettings instance, not thread-safe.
        """
        if self.__settings is None:
            self.__settings = SystemSettings()
        return self.__settings

    @classmethod
    def _read_checksum_file(cls, path, enc=None, maxlen=4096):
        """
        Read checksum file at path, return content as string.
        """
        if enc is None:
            enc = etpConst['conf_encoding']
        with codecs.open(path, "r", encoding=enc) as f_down:
            try:
                return f_down.read(maxlen).strip().split()[0]
            except (OSError, IOError, IndexError,):
                return None

    def _generic_download(self, url, save_to, show_speed = True):
        """
        Generic, secure, URL download method.

        @param url: download URL
        @type url: string
        @param save_to: path to save file
        @type save_to: string
        @keyword show_speed: if True, download speed will be shown
        @type show_speed: bool
        @return: download status (True if download succeeded)
        @rtype: bool
        """
        fetch_errors = (
            UrlFetcher.TIMEOUT_FETCH_ERROR,
            UrlFetcher.GENERIC_FETCH_ERROR,
            UrlFetcher.GENERIC_FETCH_WARN,
        )
        fetcher = self._entropy._url_fetcher(url, save_to, resume = False,
            show_speed = show_speed)
        rc_fetch = fetcher.download()
        if rc_fetch in fetch_errors:
            return False
        # setup permissions
        const_setup_file(save_to, etpConst['entropygid'], 0o664)
        return True

    def _install_gpg_key(self, repo_sec, package_gpg_pubkey):

        pk_expired = False
        try:
            pk_avail = repo_sec.is_pubkey_available(self._url)
        except repo_sec.KeyExpired:
            pk_avail = False
            pk_expired = True

        def do_warn_user(fingerprint):
            mytxt = purple(
                _("Make sure to verify the imported "
                  "key and set an appropriate trust level"))
            self._entropy.output(
                mytxt + ":",
                level = "warning",
                header = red("   # ")
            )
            mytxt = brown("gpg --homedir '%s' --edit-key '%s'" % (
                self._gpg_keystore_dir, fingerprint,)
            )
            self._entropy.output(
                "$ " + mytxt,
                level = "warning",
                header = red("   # ")
            )

        easy_url = "N/A"
        splitres = entropy.tools.spliturl(self._url)
        if hasattr(splitres, 'netloc'):
            easy_url = splitres.netloc

        if pk_avail:

            tmp_dir = const_mkdtemp()
            repo_tmp_sec = self._entropy.RepositorySecurity(
                keystore_dir = tmp_dir)
            # try to install and get fingerprint
            try:
                downloaded_key_fp = repo_tmp_sec.install_key(
                    self._url, package_gpg_pubkey)
            except repo_sec.GPGError:
                downloaded_key_fp = None

            fingerprint = repo_sec.get_key_metadata(
                self._url)['fingerprint']
            shutil.rmtree(tmp_dir, True)

            if downloaded_key_fp != fingerprint and \
                (downloaded_key_fp is not None):
                mytxt = "%s: %s !!!" % (
                    purple(_("GPG key changed for")),
                    bold(easy_url),
                )
                self._entropy.output(
                    mytxt,
                    level = "warning",
                    header = red("   # ")
                )
                mytxt = "[%s => %s]" % (
                    darkgreen(fingerprint),
                    purple(downloaded_key_fp),
                )
                self._entropy.output(
                    mytxt,
                    level = "warning",
                    header = red("   # ")
                )
            else:
                mytxt = "%s: %s" % (
                    purple(_("GPG key already installed for")),
                    bold(easy_url),
                )
                self._entropy.output(
                    mytxt,
                    level = "info",
                    header = red("   # ")
                )
            do_warn_user(fingerprint)
            return True

        elif pk_expired:
            mytxt = "%s: %s" % (
                purple(_("GPG key EXPIRED for URL")),
                bold(easy_url),
            )
            self._entropy.output(
                mytxt,
                level = "warning",
                header = red("   # ")
            )

        # actually install
        mytxt = "%s: %s" % (
            purple(_("Installing GPG key for URL")),
            brown(easy_url),
        )
        self._entropy.output(
            mytxt,
            level = "info",
            header = red("   # "),
            back = True
        )
        try:
            fingerprint = repo_sec.install_key(self._url,
                package_gpg_pubkey)
        except repo_sec.GPGError as err:
            mytxt = "%s: %s" % (
                darkred(_("Error during GPG key installation")),
                err,
            )
            self._entropy.output(
                mytxt,
                level = "error",
                header = red("   # ")
            )
            return False

        mytxt = "%s: %s" % (
            purple(_("Successfully installed GPG key for URL")),
            brown(easy_url),
        )
        self._entropy.output(
            mytxt,
            level = "info",
            header = red("   # ")
        )
        mytxt = "%s: %s" % (
            darkgreen(_("Fingerprint")),
            bold(fingerprint),
        )
        self._entropy.output(
            mytxt,
            level = "info",
            header = red("   # ")
        )
        do_warn_user(fingerprint)
        return True

    def _verify_gpg(self, package, package_gpg_pubkey, package_gpg_sign):

        try:
            repo_sec = self._entropy.RepositorySecurity(
                keystore_dir = self._gpg_keystore_dir)
        except Repository.GPGError:
            return None # GPG not available

        installed = self._install_gpg_key(repo_sec, package_gpg_pubkey)
        if not installed:
            return None

        # verify GPG now
        gpg_good, err_msg = repo_sec.verify_file(self._url,
            package, package_gpg_sign)
        if not gpg_good:
            mytxt = "%s: %s" % (
                purple(_("Error during GPG verification of")),
                os.path.basename(package),
            )
            self._entropy.output(
                mytxt,
                level = "error",
                header = red("   # ") + bold(" !!! ")
            )
            mytxt = "%s: %s" % (
                purple(_("It could mean a potential security risk")),
                err_msg,
            )
            self._entropy.output(
                mytxt,
                level = "error",
                header = red("   # ") + bold(" !!! ")
            )
            return False

        mytxt = "%s: %s." % (
            bold(_("Security Advisories")),
            purple(_("GPG key verification successful")),
        )
        self._entropy.output(
            mytxt,
            level = "info",
            header = red("   # ")
        )

        return True

    def _validate_cache(self):
        """
        Validate cache by looking at some checksum data
        """
        inst_pkgs_cksum = self._entropy.installed_repository().checksum(
            do_order = True, strict = False)
        repo_cksum = self._entropy._repositories_hash()

        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring(repo_cksum + inst_pkgs_cksum))
        cache_key = "_security_validate_cache_%s" % (sha.hexdigest(),)

        cached = self._cacher.pop(cache_key, cache_dir = self._CACHE_DIR)
        if cached is None:
            self.clear() # kill the cache
        self._cacher.push(cache_key, True, cache_dir = self._CACHE_DIR)

    def clear(self):
        """
        Clear instance cache (RAM and on-disk).
        """
        self._adv_metadata = None
        self._cacher.discard()
        EntropyCacher.clear_cache_item(self._CACHE_ID,
            cache_dir = self._CACHE_DIR)

        self._setup_paths()

    def _get_advisories_cache_hash(self):
        dir_checksum = entropy.tools.md5sum_directory(
            self.SECURITY_DIR)

        sha = hashlib.sha1()

        cache_s = "b{%s}dc{%s}r{%s}" % (
            self._settings['repositories']['branch'],
            dir_checksum, etpConst['systemroot'],
        )
        sha.update(const_convert_to_rawstring(cache_s))

        cache_key = "%s%s" % (self._CACHE_ID, sha.hexdigest(),)
        return cache_key

    def get_advisories_cache(self):
        """
        Return cached advisories information metadata. It first tries to load
        them from RAM and, in case of failure, it tries to gather the info
        from disk, using EntropyCacher.
        """
        if self._adv_metadata is not None:
            return self._adv_metadata.copy()

        # validate cache
        self._validate_cache()

        c_hash = self._get_advisories_cache_hash()
        adv_metadata = self._cacher.pop(c_hash,
            cache_dir = self._CACHE_DIR)
        if adv_metadata is not None:
            self._adv_metadata = adv_metadata
            return self._adv_metadata.copy()

    def set_advisories_cache(self, adv_metadata):
        """
        Set advisories information metadata cache.

        @param adv_metadata: advisories metadata to store
        @type adv_metadata: dict
        """
        self._adv_metadata = None
        c_hash = self._get_advisories_cache_hash()
        # async false to allow 3rd-party applications to not wait
        # before getting cached results. A straight example: sulfur
        # and its security cache generation separate thread.
        self._cacher.push(c_hash, adv_metadata,
            cache_dir = self._CACHE_DIR, async = False)

    def _get_advisories_list(self):
        """
        Return a list of advisory files. Internal method.
        """
        if not self.check_advisories_availability():
            return []
        xmls = os.listdir(self.SECURITY_DIR)
        xmls = sorted([x for x in xmls if x.endswith(".xml") and \
            x.startswith("glsa-")])
        return xmls

    def get_advisories_metadata(self, use_cache = True, quiet = False):
        """
        Get security advisories metadata.

        @return: advisories metadata
        @rtype: dict
        """
        if use_cache:
            cached = self.get_advisories_cache()
            if cached is not None:
                return cached

        adv_metadata = {}
        xmls = self._get_advisories_list()
        maxlen = len(xmls)
        count = 0
        t_up = time.time()
        for xml in xmls:

            count += 1
            if quiet:
                cur_t = time.time()
                if ((cur_t - t_up) > 1):
                    t_up = cur_t
                    self._entropy.output(":: " + \
                        str(round((float(count)/maxlen)*100, 1)) + "% ::",
                        importance = 0, level = "info", back = True)

            xml_metadata = None
            exc_string = ""
            exc_err = ""
            try:
                xml_metadata = self.__get_xml_metadata(xml)
            except KeyboardInterrupt:
                return {}
            except Exception as err:
                exc_string = str(Exception)
                exc_err = str(err)
            if xml_metadata == None:
                more_info = ""
                if exc_string:
                    mytxt = _("Error")
                    more_info = " %s: %s: %s" % (mytxt, exc_string, exc_err,)
                mytxt = "%s: %s: %s! %s" % (
                    blue(_("Warning")),
                    bold(xml),
                    blue(_("advisory broken")),
                    more_info,
                )
                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = red(" !!! ")
                )
                continue
            elif not xml_metadata:
                continue
            adv_metadata.update(xml_metadata)

        adv_metadata = self._filter_advisories(adv_metadata)
        self.set_advisories_cache(adv_metadata)
        self._adv_metadata = adv_metadata.copy()
        return adv_metadata

    def _filter_advisories(self, adv_metadata):
        """
        This function filters advisories metadata dict removing non-applicable
        ones.

        @param adv_metadata: security advisories metadata dict
        @type adv_metadata: dict
        @return: filtered security advisories metadata
        @rtype: dict
        """
        # do not match package repositories, never consider them in updates!
        # that would be a nonsense, since package repos are temporary.
        enabled_repos = self._entropy._filter_available_repositories()
        match_repos = tuple([x for x in \
            self._settings['repositories']['order'] if x in enabled_repos])

        keys = list(adv_metadata.keys())
        for key in keys:
            valid = True
            if adv_metadata[key]['affected']:
                affected = adv_metadata[key]['affected']
                affected_keys = list(affected.keys())
                valid = False
                skipping_keys = set()
                for a_key in affected_keys:
                    match = self._entropy.atom_match(a_key,
                        match_repo = match_repos)
                    if match[0] != -1:
                        # it's in the repos, it's valid
                        valid = True
                    else:
                        skipping_keys.add(a_key)
                if not valid:
                    del adv_metadata[key]
                for a_key in skipping_keys:
                    try:
                        del adv_metadata[key]['affected'][a_key]
                    except KeyError:
                        continue
                try:
                    if not adv_metadata[key]['affected']:
                        del adv_metadata[key]
                except KeyError:
                    continue

        return adv_metadata

    def is_affected(self, adv_key, adv_data = None):
        """
        Determine whether the system is affected by vulnerabilities listed
        in the provided security advisory identifier.

        @param adv_key: security advisories identifier
        @type adv_key: string
        @keyword adv_data: use the provided security advisories instead of
            the stored one.
        @type adv_data: dict
        @return: True, if system is affected by vulnerabilities listed in the
            provided security advisory.
        @rtype: bool
        """
        if not adv_data:
            adv_data = self.get_advisories_metadata()
        if adv_key not in adv_data:
            return False
        mydata = adv_data[adv_key].copy()
        del adv_data

        if not mydata['affected']:
            return False

        for key in mydata['affected']:

            vul_atoms = mydata['affected'][key][0]['vul_atoms']
            unaff_atoms = mydata['affected'][key][0]['unaff_atoms']
            unaffected_atoms = set()
            if not vul_atoms:
                return False
            for atom in unaff_atoms:
                matches = self._entropy.installed_repository().atomMatch(atom,
                    multiMatch = True)
                for idpackage in matches[0]:
                    unaffected_atoms.add((idpackage, 0))

            for atom in vul_atoms:
                match = self._entropy.installed_repository().atomMatch(atom)
                if (match[0] != -1) and (match not in unaffected_atoms):
                    self._affected_pkgs.add(atom)
                    return True
        return False

    def get_vulnerabilities(self):
        """
        Return advisories metadata for installed packages containing
        vulnerabilities.

        @return: advisories metadata for vulnerable packages.
        @rtype: dict
        """
        return self.__get_affection()

    def get_fixed_vulnerabilities(self):
        """
        Return advisories metadata for installed packages not affected
        by any vulnerability.

        @return: advisories metadata for NON-vulnerable packages.
        @rtype: dict
        """
        return self.__get_affection(affected = False)

    def __get_affection(self, affected = True):
        """
        If not affected: not affected packages will be returned.
        If affected: affected packages will be returned.
        """
        adv_data = self.get_advisories_metadata()
        adv_data_keys = list(adv_data.keys())
        valid_keys = set()
        for adv in adv_data_keys:
            is_affected = self.is_affected(adv, adv_data)
            if affected == is_affected:
                valid_keys.add(adv)
        # we need to filter our adv_data and return
        for key in adv_data_keys:
            if key not in valid_keys:
                try:
                    del adv_data[key]
                except KeyError:
                    pass
        # now we need to filter packages in adv_dat
        for adv in adv_data:
            for key in list(adv_data[adv]['affected'].keys()):
                atoms = adv_data[adv]['affected'][key][0]['vul_atoms']
                applicable = True
                for atom in atoms:
                    if atom in self._affected_pkgs:
                        applicable = False
                        break
                if applicable == affected:
                    del adv_data[adv]['affected'][key]
        return adv_data

    def get_affected_packages(self):
        """
        Return a list of package names affected by vulnerabilities.

        @return: list (set) of package names affected by vulnerabilities
        @rtype: set
        """
        adv_data = self.get_advisories_metadata()
        adv_data_keys = list(adv_data.keys())
        del adv_data
        self._affected_pkgs.clear()
        for key in adv_data_keys:
            self.is_affected(key)
        return self._affected_pkgs

    def __get_xml_metadata(self, xmlfilename):
        """
        Parses a Gentoo GLSA XML file extracting advisory metadata.

        @param xmlfilename: GLSA filename
        @type xmlfilename: string
        @return: advisory metadata extracted
        @rtype: dict
        """
        from xml.dom import minidom

        xml_data = {}
        xmlfile = os.path.join(self.SECURITY_DIR, xmlfilename)
        try:
            xmldoc = minidom.parse(xmlfile)
        except (IOError, OSError, TypeError, AttributeError,):
            return None

        # get base data
        glsa_tree = xmldoc.getElementsByTagName("glsa")[0]
        glsa_product = glsa_tree.getElementsByTagName("product")[0]
        if glsa_product.getAttribute("type") != "ebuild":
            return {}

        glsa_id = glsa_tree.getAttribute("id")
        glsa_title = glsa_tree.getElementsByTagName("title")[0]
        glsa_title = glsa_title.firstChild.data
        glsa_synopsis = glsa_tree.getElementsByTagName("synopsis")[0]
        glsa_synopsis = glsa_synopsis.firstChild.data
        glsa_announced = glsa_tree.getElementsByTagName("announced")[0]
        glsa_announced = glsa_announced.firstChild.data
        glsa_revised = glsa_tree.getElementsByTagName("revised")[0]
        glsa_revised = glsa_revised.firstChild.data

        xml_data['filename'] = xmlfilename
        xml_data['url'] = "http://www.gentoo.org/security/en/glsa/%s" % (
            xmlfilename,)
        xml_data['title'] = glsa_title.strip()
        xml_data['synopsis'] = glsa_synopsis.strip()
        xml_data['announced'] = glsa_announced.strip()
        xml_data['revised'] = glsa_revised.strip()
        xml_data['bugs'] = ["https://bugs.gentoo.org/" + \
            x.firstChild.data.strip() for x in \
            glsa_tree.getElementsByTagName("bug")]

        try:
            glsa_access = glsa_tree.getElementsByTagName("access")[0]
            xml_data['access'] = glsa_access.firstChild.data.strip()
        except IndexError:
            xml_data['access'] = ""

        # references
        references = glsa_tree.getElementsByTagName("references")[0]
        xml_data['references'] = [x.getAttribute("link").strip() for x in \
            references.getElementsByTagName("uri")]

        try:
            xml_data['description_items'] = []
            desc = glsa_tree.getElementsByTagName("description")[0]
            desc = desc.getElementsByTagName("p")[0].firstChild.data.strip()
            xml_data['description'] = desc
            items = glsa_tree.getElementsByTagName("description")[0]
            for item in items.getElementsByTagName("ul"):
                li_items = item.getElementsByTagName("li")
                for li_item in li_items:
                    xml_data['description_items'].append(' '.join(
                        [x.strip() for x in \
                            li_item.firstChild.data.strip().split("\n")])
                    )
        except IndexError:
            xml_data['description'] = ""
            xml_data['description_items'] = []

        try:
            workaround = glsa_tree.getElementsByTagName("workaround")[0]
            workaround_p = workaround.getElementsByTagName("p")[0]
            xml_data['workaround'] = workaround_p.firstChild.data.strip()
        except IndexError:
            xml_data['workaround'] = ""

        try:
            xml_data['resolution'] = []
            resolution = glsa_tree.getElementsByTagName("resolution")[0]
            p_elements = resolution.getElementsByTagName("p")
            for p_elem in p_elements:
                xml_data['resolution'].append(p_elem.firstChild.data.strip())
        except IndexError:
            xml_data['resolution'] = []

        try:
            impact = glsa_tree.getElementsByTagName("impact")[0]
            impact_p = impact.getElementsByTagName("p")[0]
            xml_data['impact'] = impact_p.firstChild.data.strip()
        except IndexError:
            xml_data['impact'] = ""
        impact_type = glsa_tree.getElementsByTagName("impact")[0]
        xml_data['impacttype'] = impact_type.getAttribute("type").strip()

        try:
            background = glsa_tree.getElementsByTagName("background")[0]
            background_p = background.getElementsByTagName("p")[0]
            xml_data['background'] = background_p.firstChild.data.strip()
        except IndexError:
            xml_data['background'] = ""

        # affection information
        affected = glsa_tree.getElementsByTagName("affected")[0]
        affected_packages = {}
        # we will then filter affected_packages using repositories information
        # if not affected_packages: advisory will be dropped
        for pkg in affected.getElementsByTagName("package"):
            name = pkg.getAttribute("name")
            if name not in affected_packages:
                affected_packages[name] = []

            pdata = {}
            pdata["arch"] = pkg.getAttribute("arch").strip()
            pdata["auto"] = (pkg.getAttribute("auto") == "yes")
            pdata["vul_vers"] = [self.__make_version(v) for v in \
                pkg.getElementsByTagName("vulnerable")]
            pdata["unaff_vers"] = [self.__make_version(v) for v in \
                pkg.getElementsByTagName("unaffected")]
            pdata["vul_atoms"] = [self.__make_atom(name, v) for v \
                in pkg.getElementsByTagName("vulnerable")]
            pdata["unaff_atoms"] = [self.__make_atom(name, v) for v \
                in pkg.getElementsByTagName("unaffected")]
            affected_packages[name].append(pdata)
        xml_data['affected'] = affected_packages.copy()

        return {glsa_id: xml_data}

    def __make_version(self, vnode):
        """
        creates from the information in the I{versionNode} a
        version string (format <op><version>).

        @param vnode: a <vulnerable> or <unaffected> Node that
            contains the version information for this atom
        @type vnode: xml.dom.Node
        @return: the version string
        @rtype: string
        """
        return self._op_mappings[vnode.getAttribute("range")] + \
            vnode.firstChild.data.strip()

    def __make_atom(self, pkgname, vnode):
        """
        creates from the given package name and information in the
        I{versionNode} a (syntactical) valid portage atom.

        @param pkgname: the name of the package for this atom
        @type pkgname: string
        @param vnode: a <vulnerable> or <unaffected> Node that
            contains the version information for this atom
        @type vnode: xml.dom.Node
        @return: the portage atom
        @rtype: string
        """
        return str(self._op_mappings[vnode.getAttribute("range")] + pkgname + \
            "-" + vnode.firstChild.data.strip())

    def check_advisories_availability(self):
        """
        Return whether security advisories are available.

        @return: availability
        @rtype: bool
        """
        return os.path.isdir(self.SECURITY_DIR)

    def sync(self, do_cache = True, force = False):
        """
        This is the service method for remotely fetch advisories metadata.

        @keyword do_cache: generates advisories cache
        @type do_cache: bool
        @return: execution status (0 means all file)
        @rtype: int
        """
        mytxt = "%s: %s %s" % (
            bold(_("Security Advisories")),
            blue(_("getting latest advisories")),
            red("..."),
        )
        self._entropy.output(
            mytxt,
            importance = 2,
            level = "info",
            header = red(" @@ ")
        )

        workdir = None
        try:
            try:
                workdir = const_mkdtemp(prefix="security-")
            except (OSError, IOError) as err:
                self._entropy.output(
                    "%s: %s" % (
                        darkred(_("cannot create temporary directory")),
                        err,
                    ),
                    importance = 2,
                    level = "error",
                    header = red(" @@ ")
                )
                return 1

            rc_lock, updated = self._fetch(workdir, force = force)

        finally:
            if workdir is not None:
                shutil.rmtree(workdir, True)

        if rc_lock == 0:
            if updated:
                advtext = "%s: %s" % (
                    bold(_("Security Advisories")),
                    darkgreen(_("updated successfully")),
                )
                if do_cache:
                    self.get_advisories_metadata()
            else:
                advtext = "%s: %s" % (
                    bold(_("Security Advisories")),
                    darkgreen(_("already up to date")),
                )
            self._entropy.output(
                advtext,
                importance = 2,
                level = "info",
                header = red(" @@ ")
            )
        return rc_lock

    def _setup_paths(self):
        """
        Setup Entropy Security directory and file paths.
        """
        sec_dir = self.SECURITY_DIR
        if not os.path.isdir(sec_dir) and os.path.lexists(sec_dir):
            os.remove(sec_dir)
        const_setup_directory(sec_dir)

        cache_dir = self._CACHE_DIR
        if not os.path.isdir(cache_dir) and os.path.lexists(cache_dir):
            os.remove(cache_dir)
        const_setup_directory(cache_dir)

    def _clear_security_dir(self):
        """
        Remove the content of the security directory.
        """
        sec_dir = self.SECURITY_DIR
        for name in os.listdir(sec_dir):
            path = os.path.join(sec_dir, name)
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
            else:
                shutil.rmtree(path, True)

    def _fetch(self, tempdir, force = False):
        """
        Download the GLSA advisories, verify their integrity and origin.
        """
        self._setup_paths()
        self._clear_security_dir()

        md5_ext = etpConst['packagesmd5fileext']
        url_checksum = self._url + md5_ext
        security_file = os.path.basename(self._url)
        updated = False

        package = os.path.join(tempdir, security_file)
        package_checksum = package + md5_ext
        old_package_checksum = os.path.join(
            self._CACHE_DIR, package_checksum)

        url_gpg_sign = self._url + etpConst['etpgpgextension']
        package_gpg_sign = package + etpConst['etpgpgextension']

        url_gpg_pubkey = os.path.join(
            os.path.dirname(self._url),
            etpConst['etpdatabasegpgfile'])
        package_gpg_pubkey = os.path.join(
            tempdir, "security-advisories#" + etpConst['etpdatabasegpgfile'])

        status = self._generic_download(
            url_checksum, package_checksum,
            show_speed = False)
        if not status:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("cannot download checksum, sorry")),
            )
            self._entropy.output(
                mytxt,
                importance = 2,
                level = "error",
                header = red("   ## ")
            )
            return 2, updated

        previous_checksum = self._read_checksum_file(old_package_checksum)
        checksum = self._read_checksum_file(package_checksum)
        if (checksum == previous_checksum) and not force:
            return 0, updated

        # download package
        status =  self._generic_download(self._url, package)
        if not status:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("unable to download advisories, sorry")),
            )
            self._entropy.output(
                mytxt,
                importance = 2,
                level = "error",
                header = red("   ## ")
            )
            return 1, updated

        mytxt = "%s: %s %s" % (
            bold(_("Security Advisories")),
            blue(_("Verifying checksum")),
            red("..."),
        )
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red("   # "),
            back = True
        )

        # verify digest
        checksum = self._read_checksum_file(package_checksum)
        if checksum != previous_checksum:
            updated = True

        md5res = entropy.tools.compare_md5(package, checksum)
        if md5res:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkgreen(_("verification successful")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = red("   # ")
            )
        else:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("checksum verification failed, sorry")),
            )
            self._entropy.output(
                mytxt,
                importance = 2,
                level = "error",
                header = red("   ## ")
            )
            return 5, updated

        # download GPG key and package signature in a row
        # env hook, disable GPG check
        if self._gpg_feature:
            gpg_sign_sts = self._generic_download(
                url_gpg_sign, package_gpg_sign,
                show_speed = False)
            gpg_key_sts = self._generic_download(
                url_gpg_pubkey, package_gpg_pubkey,
                show_speed = False)
            if gpg_sign_sts and gpg_key_sts:
                verify_sts = self._verify_gpg(
                    package, package_gpg_pubkey, package_gpg_sign)
                if verify_sts is None:
                    mytxt = "%s: %s." % (
                        bold(_("Security Advisories")),
                        purple(_("GPG service not available")),
                    )
                    self._entropy.output(
                        mytxt,
                        level = "info",
                        header = red("   # ")
                    )
                elif not verify_sts:
                    return 7, updated

        try:
            os.rename(package_checksum, old_package_checksum)
        except OSError as err:
            if err.errno != errno.EXDEV:
                raise
            shutil.copy2(package_checksum, old_package_checksum)
        const_setup_file(old_package_checksum,
            etpConst['entropygid'], 0o664)

        status = entropy.tools.uncompress_tarball(
            package,
            extract_path = self.SECURITY_DIR,
            catch_empty = True
        )
        if status != 0:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("digest verification failed, try again later")),
            )
            self._entropy.output(
                mytxt,
                importance = 2,
                level = "error",
                header = red("   ## ")
            )
            return 6, updated

        self.clear()
        return 0, updated


class Repository:

    """
    This class provides a very simple Entropy repositories authenticity
    mechanism based on public-key authentication. Using this class you can
    sign or verify repository files.
    This is the core class for public-key based repository security support.
    Encryption is based on the RSA 2048bit algorithm.

    NOTE: default GNUPGHOME is set to "/etc/entropy/gpg-keys".
    NOTE: this class requires gnupg installed.
    NOTE: thanks to http://code.google.com/p/python-gnupg project for providing
        a nice testing codebase.
    """

    class GPGError(EntropyException):
        """Errors during GPG commands execution"""

    class GPGServiceNotAvailable(GPGError):
        """A particular feature or service is not available"""

    class NothingImported(GPGError):
        """Public/private key not imported"""

    class KeyAlreadyInstalled(GPGError):
        """Public/private key already installed"""

    class KeyExpired(GPGError):
        """Public/private key is expired!"""

    class ListKeys(list):
        ''' Handle status messages for --list-keys.

            Handle pub and uid (relating the latter to the former).

            Don't care about (info from src/DETAILS):

            crt = X.509 certificate
            crs = X.509 certificate and private key available
            sub = subkey (secondary key)
            ssb = secret subkey (secondary key)
            uat = user attribute (same as user id except for field 10).
            sig = signature
            rev = revocation signature
            pkd = public key data (special field format, see below)
            grp = reserved for gpgsm
            rvk = revocation key
        '''
        def __init__(self):
            list.__init__(self)
            self.curkey = None
            self.fingerprints = []

        def key(self, args):
            myvars = ("""
                type trust length algo keyid date expires dummy ownertrust uid
            """).split()
            self.curkey = {}
            for i in range(len(myvars)):
                self.curkey[myvars[i]] = args[i]
            self.curkey['uids'] = [self.curkey['uid']]
            del self.curkey['uid']
            self.append(self.curkey)

        pub = sec = key

        def fpr(self, args):
            self.curkey['fingerprint'] = args[9]
            self.fingerprints.append(args[9])

        def uid(self, args):
            self.curkey['uids'].append(args[9])

        def handle_status(self, key, value):
            pass

    _GPG_EXEC = "/usr/bin/gpg"
    GPG_HOME = os.path.join(etpConst['confdir'], "gpg-keys")

    def __init__(self, keystore_dir = None):
        """
        Instance constructor.

        @param repository_identifier: Entropy unique repository identifier
        @type repository_identifier: string
        """
        self.__encbits = 2048
        if keystore_dir is None:
            self.__keystore = Repository.GPG_HOME
        else:
            self.__keystore = keystore_dir
        self.__keymap_file = os.path.join(self.__keystore, "entropy.keymap")
        self.__key_list_cache = None

        # setup repositories keys dir
        if not os.path.isdir(self.__keystore) and not \
            os.path.lexists(self.__keystore):
            try:
                os.makedirs(self.__keystore, 0o775)
            except OSError as err:
                if err.errno != errno.EACCES:
                    raise
                raise Repository.GPGServiceNotAvailable(err)

        # try to setup proper permissions, gpg is a pita
        try:
            const_setup_perms(self.__keystore, etpConst['entropygid'],
                f_perms = 0o660)
        except (IOError, OSError,):
            raise Repository.GPGServiceNotAvailable(
                "cannot setup permissions for %s" % (self.__keystore,))

        if not const_file_readable(Repository._GPG_EXEC):
            raise Repository.GPGServiceNotAvailable("no gnupg installed")

        import socket
        self.__socket = socket

    def __get_date_after_days(self, days):
        """
        Given a time delta expressed in days, return new ISO date string.
        """
        exp_date = datetime.date.today() + datetime.timedelta(days)
        year = str(exp_date.year)
        month = str(exp_date.month)
        day = str(exp_date.day)
        if len(day) < 2:
            day = '0' + day
        if len(month) < 2:
            month = '0' + month
        return "%s-%s-%s" % (year, month, day,)

    def __is_str_unixtime_in_the_past(self, unixtime):
        today = datetime.date.today()
        unix_date = datetime.date.fromtimestamp(float(unixtime))
        return today > unix_date

    def __get_keymap(self):
        """
        Read Entropy keys <-> repository map from keymap file.
        """
        keymap = {}
        if not os.path.isfile(self.__keymap_file):
            return keymap

        with open(self.__keymap_file, "r") as key_f:
            for line in key_f.readlines():
                try:
                    my_repoid, my_fp = line.strip().split()
                except ValueError:
                    continue
                keymap[my_repoid] = my_fp
        return keymap

    def __write_keymap(self, new_keymap):
        """
        Write Entropy keys <-> repository map to keymap file.
        """
        # write back, safely
        self.__key_list_cache = None
        tmp_path = self.__keymap_file+".entropy.tmp"
        enc = etpConst['conf_encoding']
        with codecs.open(tmp_path, "w", encoding=enc) as key_f:
            for key, fp in new_keymap.items():
                key_f.write("%s %s\n" % (key, fp,))
        # atomic
        os.rename(tmp_path, self.__keymap_file)
        const_setup_perms(self.__keymap_file, etpConst['entropygid'])

    def __update_keymap(self, repoid, fingerprint):
        """
        Update Entropy keys <-> repository mapping, add mapping between
        repoid and fingerprint.
        """
        keymap = self.__get_keymap()
        keymap[repoid] = fingerprint
        self.__write_keymap(keymap)

    def __remove_keymap(self, repoid):
        """
        Remove repository identifier <-> GPG key mapping.
        """
        keymap = self.__get_keymap()
        if repoid in keymap:
            del keymap[repoid]
        self.__write_keymap(keymap)

    def __list_keys(self, secret = False, homedir = None):

        which = 'keys'
        if secret:
            which = 'secret-keys'
        args = self.__default_gpg_args(homedir = homedir) + \
            ["--list-%s" % (which,), "--fixed-list-mode", "--fingerprint",
                "--with-colons"]

        proc = subprocess.Popen(args, **self.__default_popen_args())
        try:
            # wait for process to terminate
            proc_rc = proc.wait()
            if proc_rc != 0:
                raise Repository.GPGError("cannot list keys, exit status %s" % (
                    proc_rc,))

            out_data = proc.stdout.readlines()
        finally:
            self.__default_popen_close(proc)

        valid_keywords = ['pub', 'uid', 'sec', 'fpr']
        result = Repository.ListKeys()
        for line in out_data:
            line = const_convert_to_unicode(line)

            const_debug_write(__name__, "_list_keys: read => %s" % (
                line.strip(),))
            items = line.strip().split(':')
            if not items:
                continue

            keyword = items[0]
            if keyword in valid_keywords:
                getattr(result, keyword)(items)

        return result

    def get_keys(self, private = False):
        """
        Get available keys indexed by name.

        @return: available keys and their metadata
        @rtype: dict
        """
        if self.__key_list_cache is not None:
            return self.__key_list_cache.copy()

        keymap = self.__get_keymap()
        pubkeys = dict((x['fingerprint'], x,) for x in \
            self.__list_keys(secret = private))
        key_data = dict((x, pubkeys.get(y),) for x, y in keymap.items() if \
            pubkeys.get(y) is not None)
        self.__key_list_cache = key_data

        return key_data.copy()

    def __gen_key_input(self, **kwargs):
        """
        Generate --gen-key input per gpg doc/DETAILS
        """
        parms = {}
        for key, val in list(kwargs.items()):
            key = key.replace('_','-').title()
            parms[key] = val
        parms.setdefault('Key-Type','RSA')
        parms.setdefault('Key-Length', 1024)
        parms.setdefault('Name-Real', "Autogenerated Key")
        parms.setdefault('Name-Comment', "Generated by gnupg.py")
        try:
            logname = os.environ['LOGNAME']
        except KeyError:
            logname = os.environ['USERNAME']
        hostname = self.__socket.gethostname()
        parms.setdefault('Name-Email', "%s@%s" % (logname.replace(' ', '_'),
                                                  hostname))
        out = "Key-Type: %s\n" % parms.pop('Key-Type')
        for key, val in list(parms.items()):
            out += "%s: %s\n" % (key, val)
        out += "%commit\n"
        return out

        # Key-Type: RSA
        # Key-Length: 1024
        # Name-Real: ISdlink Server on %s
        # Name-Comment: Created by %s
        # Name-Email: isdlink@%s
        # Expire-Date: 0
        # %commit
        #
        #
        # Key-Type: DSA
        # Key-Length: 1024
        # Subkey-Type: ELG-E
        # Subkey-Length: 1024
        # Name-Real: Joe Tester
        # Name-Comment: with stupid passphrase
        # Name-Email: joe@foo.bar
        # Expire-Date: 0
        # Passphrase: abc
        # %pubring foo.pub
        # %secring foo.sec
        # %commit

    def __gen_key(self, key_input):
        """Generate a key; you might use gen_key_input() to create the
        control input.

        >>> gpg = GPG(gnupghome="/tmp/pygpgtest")
        >>> input = gpg.gen_key_input()
        >>> result = gpg.gen_key(input)
        >>> assert result
        >>> result = gpg.gen_key('foo')
        >>> assert not result

        """
        args = self.__default_gpg_args(preserve_perms = False) + \
            ["--status-fd", "2", "--batch", "--gen-key"]

        const_debug_write(__name__, "Repository.__gen_key args => %s" % (
            args,))
        proc = subprocess.Popen(args,
            **self.__default_popen_args(stderr = True))
        try:
            if const_is_python3():
                key_input = const_convert_to_rawstring(key_input)
            # feed gpg with data
            proc_stdout, proc_stderr = proc.communicate(input = key_input)
            # wait for process to terminate
            proc_rc = proc.wait()
        finally:
            self.__default_popen_close(proc)

        if proc_rc != 0:
            raise Repository.GPGError(
                "cannot generate key, exit status %s" % (proc_rc,))

        if const_is_python3():
            proc_stdout = const_convert_to_unicode(proc_stdout)
            proc_stderr = const_convert_to_unicode(proc_stderr)
        # now get fucking fingerprint
        key_data = [x.strip() for x in (proc_stdout+proc_stderr).split("\n") \
            if x.strip() and "KEY_CREATED" in x.split()]
        if not key_data or len(key_data) > 1:
            raise Repository.GPGError(
                "cannot grab fingerprint of newly created key, data: %s" % (
                    proc_stdout,))
        # cross fingers
        fp = key_data[0].split()[-1]
        return fp

    def create_keypair(self, repository_identifier, passphrase = None,
        name_email = None, expiration_days = None):
        """
        Create Entropy repository GPG keys and store them.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @param passphrase: passphrase to use
        @type passphrase: string
        @param name_email: email to use
        @type name_email: string
        @param expiration_days: number of days after the key expires
        @type expiration_days: int
        @return: Repository key fingerprint string
        @rtype: string
        @raise KeyError: if another keypair is already set
        """
        kwargs = {
            'key_length': self.__encbits,
            'name_real': repository_identifier,
            'name_comment': '%s [%s|%s] repository key' % (
                repository_identifier, etpConst['currentarch'],
                etpConst['product'],),
        }
        if name_email:
            kwargs['name_email'] = name_email
        if passphrase:
            kwargs['passphrase'] = passphrase
        if expiration_days:
            kwargs['expire_date'] = self.__get_date_after_days(expiration_days)

        key_input = self.__gen_key_input(**kwargs)
        key_output = self.__gen_key(key_input)

        # write to keymap
        self.__update_keymap(repository_identifier, key_output)

        # ensure permissions
        const_setup_perms(self.__keystore, etpConst['entropygid'],
            f_perms = 0o660)

        return key_output

    def get_key_metadata(self, repository_identifier, private = False):
        """
        Return key metadata for given repository identifier.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @keyword private: return metadata related to private key
        @type private: bool
        @raise KeyError: if no keys are set
        @return: key metadata
        @rtype: dict
        """
        keyring = self.get_keys(private = private)
        return keyring[repository_identifier]

    def __delete_key(self, fingerprint, secret = False):

        args = self.__default_gpg_args(preserve_perms=False) + \
            ["--batch", "--yes"]
        if secret:
            args.append("--delete-secret-key")
        else:
            args.append("--delete-key")
        args.append(fingerprint)

        const_debug_write(__name__, "Repository.__delete_key args => %s" % (
            args,))
        proc = subprocess.Popen(args, **self.__default_popen_args())
        try:
            # wait for process to terminate
            proc_rc = proc.wait()
        finally:
            self.__default_popen_close(proc)

        if proc_rc != 0:
            raise Repository.GPGError(
                "cannot delete key fingerprint %s, exit status %s" % (
                    fingerprint, proc_rc,))

    def delete_keypair(self, repository_identifier):
        """
        Delete keys (public and private) for currently set repository.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @raise KeyError: if key for given repository doesn't exist
        """
        keymap = self.__get_keymap()
        fingerprint = keymap[repository_identifier]
        self.__delete_key(fingerprint, secret = True)
        self.__delete_key(fingerprint)
        self.__remove_keymap(repository_identifier)
        # ensure permissions
        const_setup_perms(self.__keystore, etpConst['entropygid'],
            f_perms = 0o660)

    def is_pubkey_expired(self, repository_identifier):
        """
        Return whether public key is expired.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @return: True, if key is expired
        @rtype: bool
        @raise KeyError, if key is not available
        """
        ts = self.get_key_metadata(repository_identifier)
        if not ts['expires']:
            return False
        try:
            return self.__is_str_unixtime_in_the_past(ts['expires'])
        except ValueError:
            return False

    def is_privkey_expired(self, repository_identifier):
        """
        Return whether private key is expired.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @return: True, if key is expired
        @rtype: bool
        @raise KeyError, if key is not available
        """
        ts = self.get_key_metadata(repository_identifier, private = True)
        if not ts['expires']:
            return False
        try:
            return self.__is_str_unixtime_in_the_past(ts['expires'])
        except ValueError:
            return False

    def is_keypair_available(self, repository_identifier):
        """
        Return whether public and private key for given repository identifier
        is available.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @return: True, if public and private key is available
        @rtype: bool
        @raise Repository.KeyExpired: if key is expired
        """
        try:
            self.get_key_metadata(repository_identifier)
        except KeyError:
            return False
        try:
            self.get_key_metadata(repository_identifier, private = True)
        except KeyError:
            return False

        if self.is_privkey_expired(repository_identifier):
            raise Repository.KeyExpired("Key for %s is expired !" % (
                repository_identifier,))

        return True

    def is_pubkey_available(self, repository_identifier):
        """
        Return whether public key for given repository identifier is available.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @return: True, if public key is available
        @rtype: bool
        @raise Repository.KeyExpired: if key is expired
        """
        try:
            self.get_pubkey(repository_identifier)
        except KeyError:
            return False

        try:
            if self.is_pubkey_expired(repository_identifier):
                raise Repository.KeyExpired("Key for %s is expired !" % (
                    repository_identifier,))
        except Repository.GPGError:
            # wtf! something like => GPGError: cannot list keys, exit status 2
            return False
        except KeyError:
            # raised by is_pubkey_expired
            return False

        return True

    def is_privkey_available(self, repository_identifier):
        """
        Return whether private key for given repository identifier is available.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @return: True, if private key is available
        @rtype: bool
        @raise Repository.KeyExpired: if key is expired
        """
        try:
            self.get_privkey(repository_identifier)
        except KeyError:
            return False

        try:
            if self.is_privkey_expired(repository_identifier):
                raise Repository.KeyExpired("Key for %s is expired !" % (
                        repository_identifier,))
        except KeyError:
            # raised by is_privkey_expired
            return False

        return True

    def __export_key(self, fingerprint, key_type = "public"):
        """
        Export GPG keys to string.
        """

        args = self.__default_gpg_args() + ["--armor"]
        if key_type == "public":
            args += ["--export"]
        elif key_type == "private":
            args += ["--export-secret-key"]
        else:
            raise AttributeError("invalid key_type")
        args.append(fingerprint)

        proc = subprocess.Popen(args, **self.__default_popen_args())
        try:
            # wait for process to terminate
            proc_rc = proc.wait()

            if proc_rc != 0:
                raise Repository.GPGError(
                    "cannot export key which fingerprint is %s, error: %s" % (
                        fingerprint, proc_rc,))

            key_string = proc.stdout.read()
            if const_is_python3():
                key_string = const_convert_to_unicode(key_string)
            return key_string
        finally:
            self.__default_popen_close(proc)

    def get_pubkey(self, repository_identifier):
        """
        Get public key for currently set repository, if any, otherwise raise
        KeyError.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @return: public key
        @rtype: string
        @raise KeyError: if no keypair is set for repository
        """
        keymap = self.__get_keymap()
        fingerprint = keymap[repository_identifier]
        try:
            pubkey = self.__export_key(fingerprint)
        except Repository.GPGError as err:
            raise KeyError(repr(err))
        return pubkey

    def get_privkey(self, repository_identifier):
        """
        Get private key for currently set repository, if any, otherwise raise
        KeyError.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @return: private key
        @rtype: string
        @raise KeyError: if no keypair is set for repository
        """
        keymap = self.__get_keymap()
        fingerprint = keymap[repository_identifier]
        pubkey = self.__export_key(fingerprint, key_type = "private")
        return pubkey

    def get_key_fingerprint(self, key_path):
        """
        Return the fingerprint contained in the given key file, if any.
        Otherwise return None.

        @param key_path: valid path to GPG key file
        @type key_path: string
        """
        tmp_dir = None
        try:
            tmp_dir = const_mkdtemp(prefix=".entropy.security.get_fp")
            args = self.__default_gpg_args(preserve_perms = False,
                homedir = tmp_dir)
            args += ["--import", key_path]

            proc = subprocess.Popen(args, **self.__default_popen_args())
            try:
                # wait for process to terminate
                proc_rc = proc.wait()
            finally:
                self.__default_popen_close(proc)

            if proc_rc != 0:
                return None

            now_keys = set([x['fingerprint'] for x in self.__list_keys(
                homedir = tmp_dir)])
            if not now_keys:
                return None
            # NOTE: not supporting multiple keys, is this a problem?
            return now_keys.pop()
        finally:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, True)

    def install_key(self, repository_identifier, key_path,
        ignore_nothing_imported = False, merge_key = False):
        """
        Add key to keyring.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @param key_path: valid path to GPG key file
        @type key_path: string
        @keyword ignore_nothing_imported: if True, ignore NothingImported
            exception
        @type ignore_nothing_imported: bool
        @keyword merge_key: add --import-options merge-only to gpg callback
        @type merge_key: bool
        @return: fingerprint
        @rtype: string
        @raise KeyAlreadyInstalled: if key is already installed
        @raise NothingImported: if key_path contains garbage
        """
        args = self.__default_gpg_args(preserve_perms = False)
        if merge_key:
            args += ["--import-options", "merge-only"]
        args += ["--import", key_path]
        try:
            current_keys = set([x['fingerprint'] for x in self.__list_keys()])
        except OSError as err:
            if err.errno == errno.EIO:
                raise Repository.GPGError(
                    "cannot list keys for %s" % (repository_identifier))
            raise

        proc = subprocess.Popen(args, **self.__default_popen_args())
        try:
            # wait for process to terminate
            proc_rc = proc.wait()
        finally:
            self.__default_popen_close(proc)

        if proc_rc != 0:
            raise Repository.GPGError(
                "cannot install key at %s, for %s" % (
                    key_path, repository_identifier))

        now_keys = set([x['fingerprint'] for x in self.__list_keys()])
        new_keys = now_keys - current_keys
        if (len(new_keys) < 1) and not ignore_nothing_imported:
            raise Repository.NothingImported(
                "nothing imported from %s, for %s" % (
                    key_path, repository_identifier,))

        nothing_imported = False
        if len(new_keys) < 1 and ignore_nothing_imported:
            nothing_imported = True

        if len(new_keys) > 1:
            raise Repository.KeyAlreadyInstalled(
                "wtf? more than one key imported from %s, for %s" % (
                    key_path, repository_identifier,))

        fp = None
        if not nothing_imported:
            fp = new_keys.pop()
            self.__update_keymap(repository_identifier, fp)
            fp = str(fp)

        # setup perms again
        const_setup_perms(self.__keystore, etpConst['entropygid'],
            f_perms = 0o660)

        return fp

    def delete_pubkey(self, repository_identifier):
        """
        Delete public key bound to given repository identifier.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @raise KeyError: if no key is set for given repository identifier
        """
        metadata = self.get_key_metadata(repository_identifier)
        self.__remove_keymap(repository_identifier)
        self.__delete_key(metadata['fingerprint'])
        # setup perms again
        const_setup_perms(self.__keystore, etpConst['entropygid'],
            f_perms = 0o660)

    def __default_gpg_args(self, preserve_perms = True, homedir = None):
        if homedir is None:
            homedir = self.__keystore
        args = [Repository._GPG_EXEC, "--no-tty", "--no-permission-warning",
            "--no-greeting", "--homedir", homedir]
        if preserve_perms:
            args.append("--preserve-permissions")
        return args

    def __default_popen_args(self, stderr = False):
        kwargs = {
            'stdout': subprocess.PIPE,
            'stdin': subprocess.PIPE,
        }
        if not const_debug_enabled() or stderr:
            kwargs['stderr'] = subprocess.PIPE
        return kwargs

    def __default_popen_close(self, proc):
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()
        if proc.stdin is not None:
            proc.stdin.close()

    def __sign_file(self, file_path, fingerprint):

        args = self.__default_gpg_args() + ["-sa", "--detach-sign"]
        if fingerprint:
            args += ["--default-key", fingerprint]

        args.append(file_path)
        const_debug_write(__name__, "Repository.__sign_file args => %s" % (
            args,))

        asc_path = file_path + etpConst['etpgpgextension']
        # remove previously stored .asc
        if os.path.isfile(asc_path):
            const_debug_write(__name__,
                "Repository.__sign_file had to rm %s" % (asc_path,))
            os.remove(asc_path)


        proc = subprocess.Popen(args, **self.__default_popen_args())
        try:
            # wait for process to terminate
            proc_rc = proc.wait()

            if proc_rc != 0:
                raise Repository.GPGError(
                    "cannot sign file %s, exit status %s" % (
                        file_path, proc_rc,))

            if not os.path.isfile(asc_path):
                raise OSError("cannot find %s" % (asc_path,))

            return asc_path

        finally:
            self.__default_popen_close(proc)

    def sign_file(self, repository_identifier, file_path):
        """
        Sign given file path using key of given repository identifier.
        A custom passphrase can be provided as string.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @param file_path: path to file to sign
        @type file_path: string
        @return: path to signature file
        @rtype: string
        @raise KeyError: if repository key is not available
        """
        metadata = self.get_key_metadata(repository_identifier)
        return self.__sign_file(file_path, metadata['fingerprint'])

    def __verify_file(self, file_path, signature_path, fingerprint):

        args = self.__default_gpg_args()
        if fingerprint:
            args += ["--default-key", fingerprint]
        args += ["--verify", signature_path, file_path]
        const_debug_write(__name__, "Repository.__verify_file args => %s" % (
            args,))

        proc = subprocess.Popen(args, **self.__default_popen_args())
        try:
            # wait for process to terminate
            proc_rc = proc.wait()

            if proc_rc != 0:
                raise Repository.GPGError("cannot verify file %s, exit status %s" % (
                    file_path, proc_rc,))
        finally:
             self.__default_popen_close(proc)

    def verify_file(self, repository_identifier, file_path, signature_path):
        """
        Verify file in file_path usign signature in signature_path and key from
        repository_identifier.

        @param repository_identifier: repository identifier
        @type repository_identifier: string
        @param file_path: path to file to verify
        @type file_path: string
        @param signature_path: path to signature to verify
        @type signature_path: string
        @return: a tuple composed by (validity_bool, error message,)
        @rtype: tuple
        @raise KeyError: if repository key is not available
        """
        metadata = self.get_key_metadata(repository_identifier)
        try:
            self.__verify_file(file_path, signature_path, metadata['fingerprint'])
        except Repository.GPGError as err:
            const_debug_write(__name__, "Repository.verify_file error: %s" % (
                err,))
            return False, str(err)
        return True, ''
