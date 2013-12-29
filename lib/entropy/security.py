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
import hashlib
import os
import shutil
import subprocess
import time
import threading
import xml.dom.minidom

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
from entropy.locks import ResourceLock

import entropy.tools


class SystemResourcesLock(ResourceLock):
    """
    System security resources lock that can be used to acquire exclusive
    or shared access to the System data.
    """

    def __init__(self, output=None):
        """
        Object constructor.

        @keyword output: a TextInterface interface
        @type output: entropy.output.TextInterface or None
        """
        super(SystemResourcesLock, self).__init__(
            output=output)

    def path(self):
        """
        Return the path to the lock file.
        """
        return os.path.join(etpConst['entropyrundir'],
                            '.entropy.security.System.lock')


def systemexclusive(method):
    """
    Decorator used to acquire an exclusive lock through SystemResourcesLock.
    """
    def wrapped(*args, **kwargs):
        lock = SystemResourcesLock()
        with lock.exclusive():
            return method(*args, **kwargs)

    return wrapped


def systemshared(method):
    """
    Decorator used to acquire an exclusive lock through SystemResourcesLock.
    """
    def wrapped(*args, **kwargs):
        lock = SystemResourcesLock()
        with lock.shared():
            return method(*args, **kwargs)

    return wrapped


class System(object):

    """
    ~~ GIVES YOU WINGS ~~

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

    This class uses a SystemResourcesLock resource lock internally, there is
    no need for external synchronization primitives.
    """

    class UpdateError(EntropyException):
        """Raised when security advisories couldn't be updated correctly"""

    @classmethod
    def _get_xml_metadata(cls, xmlfile):
        """
        Parses a Gentoo GLSA XML file extracting advisory metadata.

        @param xmlfilename: GLSA filename
        @type xmlfilename: string
        @return: advisory metadata extracted
        @rtype: dict
        """
        xml_data = {}
        try:
            xmldoc = xml.dom.minidom.parse(xmlfile)
        except (IOError, OSError, TypeError, AttributeError,) as err:
            const_debug_write(
                __name__, "_get_xml_metadata, error: %s" % (err,))
            return None

        glsa_tree = xmldoc.getElementsByTagName("glsa")[0]
        glsa_product = glsa_tree.getElementsByTagName("product")[0]
        if glsa_product.getAttribute("type") != "ebuild":
            return None

        glsa_id = glsa_tree.getAttribute("id")
        xml_data['__id__'] = glsa_id

        glsa_title = glsa_tree.getElementsByTagName("title")[0]
        glsa_title = glsa_title.firstChild.data
        glsa_synopsis = glsa_tree.getElementsByTagName("synopsis")[0]
        glsa_synopsis = glsa_synopsis.firstChild.data
        glsa_announced = glsa_tree.getElementsByTagName("announced")[0]
        glsa_announced = glsa_announced.firstChild.data
        glsa_revised = glsa_tree.getElementsByTagName("revised")[0]
        glsa_revised = glsa_revised.firstChild.data

        xmlfilename = os.path.basename(xmlfile)
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

        op_mappings = {
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

        def make_version(vnode):
            """
            creates from the information in the I{versionNode} a
            version string (format <op><version>).

            @param vnode: a <vulnerable> or <unaffected> Node that
                contains the version information for this atom
            @type vnode: xml.dom.Node
            @return: the version string
            @rtype: string
            """
            op = op_mappings[vnode.getAttribute("range")]
            return "%s%s" % (op, vnode.firstChild.data.strip())

        def make_atom(pkgname, vnode):
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
            op = op_mappings[vnode.getAttribute("range")]
            return "%s%s-%s" % (op, pkgname, vnode.firstChild.data.strip())

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
            pdata["vul_vers"] = [make_version(v) for v in
                                 pkg.getElementsByTagName("vulnerable")]
            pdata["unaff_vers"] = [make_version(v) for v in
                                   pkg.getElementsByTagName("unaffected")]
            pdata["vul_atoms"] = [make_atom(name, v) for v in
                                  pkg.getElementsByTagName("vulnerable")]
            pdata["unaff_atoms"] = [make_atom(name, v) for v in
                                    pkg.getElementsByTagName("unaffected")]
            affected_packages[name].append(pdata)
        xml_data['affected'] = affected_packages.copy()

        return xml_data

    def __init__(self, entropy_client, security_dir=None, url=None):
        """
        Object constructor.

        @param entropy_client: an Entropy Client based object instance
        @type entropy_client: entropy.client.interfaces.Client instance
        @keyword security_dir: the directory where security advisores are
            written and read
        @type security_dir: string or None
        @keyword url: url from where advisories are fetched from
        @type url: string or None
        """
        if security_dir is None:
            self._dir = etpConst['securitydir']
        else:
            self._dir = security_dir

        self._real_url = url

        self._cache_dir = os.path.join(
            etpConst['entropyworkdir'], "security_cache")

        self._entropy = entropy_client
        self.__cacher = None
        self.__settings = None

        self._gpg_enabled = os.getenv("ETP_DISABLE_GPG") is None
        self._gpg_keystore_dir = os.path.join(
            etpConst['confdir'], "security-advisories-keys")

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

    @property
    def _url(self):
        """
        Return the remote URL from where advisories are downloaded.
        """
        if self._real_url is None:
            return self._settings['repositories']['security_advisories_url']

        return self._real_url

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
            txt = purple(
                _("Make sure to verify the imported "
                  "key and set an appropriate trust level"))
            self._entropy.output(
                txt + ":",
                level = "warning",
                header = red("   # ")
            )
            txt = brown("gpg --homedir '%s' --edit-key '%s'" % (
                self._gpg_keystore_dir, fingerprint,)
            )
            self._entropy.output(
                "$ " + txt,
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
                txt = "%s: %s !!!" % (
                    purple(_("GPG key changed for")),
                    bold(easy_url),
                )
                self._entropy.output(
                    txt,
                    level = "warning",
                    header = red("   # ")
                )
                txt = "[%s => %s]" % (
                    darkgreen(fingerprint),
                    purple(downloaded_key_fp),
                )
                self._entropy.output(
                    txt,
                    level = "warning",
                    header = red("   # ")
                )
            else:
                txt = "%s: %s" % (
                    purple(_("GPG key already installed for")),
                    bold(easy_url),
                )
                self._entropy.output(
                    txt,
                    level = "info",
                    header = red("   # ")
                )
            do_warn_user(fingerprint)
            return True

        elif pk_expired:
            txt = "%s: %s" % (
                purple(_("GPG key EXPIRED for URL")),
                bold(easy_url),
            )
            self._entropy.output(
                txt,
                level = "warning",
                header = red("   # ")
            )

        txt = "%s: %s" % (
            purple(_("Installing GPG key for URL")),
            brown(easy_url),
        )
        self._entropy.output(
            txt,
            level = "info",
            header = red("   # "),
            back = True
        )
        try:
            fingerprint = repo_sec.install_key(self._url,
                package_gpg_pubkey)
        except repo_sec.GPGError as err:
            txt = "%s: %s" % (
                darkred(_("Error during GPG key installation")),
                err,
            )
            self._entropy.output(
                txt,
                level = "error",
                header = red("   # ")
            )
            return False

        txt = "%s: %s" % (
            purple(_("Successfully installed GPG key for URL")),
            brown(easy_url),
        )
        self._entropy.output(
            txt,
            level = "info",
            header = red("   # ")
        )
        txt = "%s: %s" % (
            darkgreen(_("Fingerprint")),
            bold(fingerprint),
        )
        self._entropy.output(
            txt,
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
            txt = "%s: %s" % (
                purple(_("Error during GPG verification of")),
                os.path.basename(package),
            )
            self._entropy.output(
                txt,
                level = "error",
                header = red("   # ") + bold(" !!! ")
            )
            txt = "%s: %s" % (
                purple(_("It could mean a potential security risk")),
                err_msg,
            )
            self._entropy.output(
                txt,
                level = "error",
                header = red("   # ") + bold(" !!! ")
            )
            return False

        txt = "%s: %s." % (
            bold(_("Security Advisories")),
            purple(_("GPG key verification successful")),
        )
        self._entropy.output(
            txt,
            level = "info",
            header = red("   # ")
        )

        return True

    def _cache_key(self, advisory_id):
        """
        Return the disk cache key that can be used to retrieve stored metadata.

        @param advisory_id: the advisory for which the cache should be fetched.
            Use "all" for the metadata containing all the advisories.
        @type advisory_id: string
        """
        sha = hashlib.sha1()

        inst_repo = self._entropy.installed_repository()
        with inst_repo.direct():
            inst_pkgs_cksum = inst_repo.checksum(
                do_order=True, strict=False)

        repo_cksum = self._entropy.repositories_checksum()

        cache_s = "rc{%s}irc{%s}b{%s}dp{%s}dt{%s}r{%s}" % (
            repo_cksum,
            inst_pkgs_cksum,
            self._settings['repositories']['branch'],
            self._dir,
            os.path.getmtime(self._dir),
            etpConst['systemroot'],
        )
        sha.update(const_convert_to_rawstring(cache_s))

        # basename protects against relative paths
        return "_advcache_%s_%s" % (
            os.path.basename(advisory_id),
            sha.hexdigest(),)

    def _get_cache(self, advisory_id):
        """
        Return cached advisories information metadata. It first tries to load
        them from RAM and, in case of failure, it tries to gather the info
        from disk, using EntropyCacher.

        @param advisory_id: the advisory for which the cache should be fetched.
            Use "all" for the metadata containing all the advisories.
        @type advisory_id: string
        """
        return self._cacher.pop(self._cache_key(advisory_id),
                                cache_dir=self._cache_dir)

    def _set_cache(self, advisory_id, data):
        """
        Set advisories information metadata cache.

        @param advisory_id: the advisory for which the cache should be fetched.
            Use "all" for the metadata containing all the advisories.
        @type advisory_id: string
        @param data: advisories metadata to store
        @type data: dict
        """
        self._cacher.push(self._cache_key(advisory_id), data,
            cache_dir=self._cache_dir)

    def _xml_list(self):
        """
        Return a sorted list of available XML advisory files.

        @return: a list of available advisory files.
        @rtype: list
        """
        try:
            xmls = os.listdir(self._dir)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
            xmls = []
        xmls = [x for x in xmls if x.endswith(".xml") and x.startswith("glsa-")]
        xmls.sort()

        return xmls

    def _id_to_xml(self, advisory_id):
        """
        Return a path to the XML file given a GLSA advisory id.
        """
        return os.path.join(self._dir, advisory_id + ".xml")

    def _xml_to_id(self, xml_path):
        """
        Return the GLSA advisory id given a path to an XML file.
        """
        return os.path.basename(xml_path)[:-len(".xml")]

    @systemshared
    def list(self):
        """
        Return a list of all the available advisory identifiers.

        @return: a list of GLSA-IDs
        @rtype: list
        """
        xmls = self._xml_list()
        ids = [x[:-len(".xml")] for x in xmls]
        return ids

    @systemshared
    def advisories(self):
        """
        Return the metadata for all the advisories.
        This method is heavy and should not be used.

        @return: advisories metadata
        @rtype: dict
        """
        metadata = self._get_cache("all")
        if metadata is None:

            metadata = {}
            for xml_path in self._xml_list():

                adv_id = self._xml_to_id(xml_path)
                xml_metadata = self.advisory(adv_id, _quiet=False)
                if xml_metadata is None:
                    continue

                metadata.update(
                    {xml_metadata['__id__']: xml_metadata}
                )

            metadata = dict((x, y) for x, y in
                            metadata.items() if self._applicable(y))
            self._set_cache("all", metadata)

        return metadata

    @systemshared
    def advisory(self, advisory_id, _quiet=True):
        """
        Return the advisory metadata for the given GLSA advisory id.
        If the advisory does not exist or is broken, None is returned.

        @return: the advisory metadata dictionary
        @rtype: dict or None
        """
        metadata = self._get_cache(advisory_id)
        if metadata is not None:
            return metadata

        xml_path = self._id_to_xml(advisory_id)
        metadata = None
        try:
            metadata = self._get_xml_metadata(xml_path)
        except Exception as err:
            if not _quiet:
                txt = "%s, %s, %s: %s" % (
                    blue(_("Warning")),
                    bold(xml_path),
                    blue(_("broken advisory")),
                    err,
                )
                self._entropy.output(
                    txt,
                    importance=1,
                    level="warning",
                    header=red(" !!! ")
                )

        if metadata is not None:
            self._set_cache(advisory_id, metadata)
        return metadata

    def _applicable(self, metadata):
        """
        Return whether the given GLSA advisory is applicable on this system.
        Basically, determine if any of the packages listed in the advisory
        is in the available repositories.

        @param metadata: a single advisory metadata dictionary
        @type metadata: dict
        """
        if not metadata['affected']:
            return False

        valid = False
        for dep in metadata['affected'].keys():
            package_id, _repository_id = self._entropy.atom_match(dep)
            if package_id != -1:
                valid = True
                break

        return valid

    @systemshared
    def affected(self, metadata):
        """
        Return a list (set) of dependencies that are currently
        affected by the GLSA in the passed advisory metadata.

        @param metadata: a single advisory metadata dictionary
        @type metadata: dict
        @return: a set of package dependencies that have been found
            in the installed packages repository
        @rtype: set
        """
        affected = set()
        inst_repo = self._entropy.installed_repository()

        if not metadata['affected']:
            return affected

        for key in metadata['affected']:

            affection = metadata['affected'][key][0]

            vul_atoms = affection['vul_atoms']
            if not vul_atoms:
                continue

            unaffected = set()

            with inst_repo.direct():
                for dep in affection['unaff_atoms']:
                    package_ids, _inst_rc = inst_repo.atomMatch(
                        dep, multiMatch=True)
                    unaffected.update(package_ids)

                for dep in vul_atoms:
                    package_id, _rc = inst_repo.atomMatch(dep)
                    if package_id != -1 and package_id not in unaffected:
                        affected.add(dep)

        return affected

    def affected_id(self, advisory_id):
        """
        Return a list (set) of dependencies that are currently
        affected by the GLSA in the passed advisory metadata.

        @param advisory_id: an advisory identifier
        @type advisory_id: string
        @return: a set of package dependencies that have been found
            in the installed packages repository
        @rtype: set
        """
        metadata = self.advisory(advisory_id)
        if metadata is None:
            return set()
        return self.affected(metadata)

    @systemshared
    def vulnerabilities(self):
        """
        Return a list (set) of advisory identifiers for which the system is
        currently vulnerable.

        @return: list (set) of advisory identifiers
        @rtype: set
        """
        return self._vulnerabilities()

    @systemshared
    def fixed_vulnerabilities(self):
        """
        Return a list (set) of advisory identifiers for which the system is
        currently not vulnerable.

        @return: list (set) of advisory identifiers
        @rtype: set
        """
        return self._vulnerabilities(applied=True)

    def _vulnerabilities(self, applied=False):
        """
        Return a list (set) of applied or unapplied advisory identifiers.

        @keyword applied: True, if the advisories to return should be those
            already applied
        @type applied: bool
        @return: a list (set) of applied or unapplied advisory identifiers.
        @rtype: set
        """
        advisory_ids = set()

        for advisory_id in self.list():
            affected = self.affected_id(advisory_id)
            if affected and not applied:
                advisory_ids.add(advisory_id)
            elif not affected and applied:
                advisory_ids.add(advisory_id)

        return advisory_ids

    @systemshared
    def available(self):
        """
        Return whether security advisories are available.

        @return: True, if advisories are available
        @rtype: bool
        """
        if self.list():
            return True
        return False

    @systemexclusive
    def update(self, force=False):
        """
        Update the local advisories by downloading a new version online.

        @return: exit code
        @rtype: int
        """
        txt = "%s: %s %s" % (
            bold(_("Security Advisories")),
            blue(_("getting latest advisories")),
            red("..."),
        )
        self._entropy.output(
            txt,
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
        sec_dir = self._dir
        cache_dir = self._cache_dir

        for dir_path in (sec_dir, cache_dir):
            try:
                const_setup_directory(dir_path)
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise

    def _clear_security_dir(self):
        """
        Remove the content of the security directory.
        """
        for name in os.listdir(self._dir):
            path = os.path.join(self._dir, name)
            try:
                os.remove(path)
            except OSError as err:
                if err.errno not in (errno.ENOENT, errno.EISDIR):
                    raise

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
            self._cache_dir, os.path.basename(package_checksum))

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
            txt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("cannot download checksum, sorry")),
            )
            self._entropy.output(
                txt,
                importance = 2,
                level = "error",
                header = red("   ## ")
            )
            return 2, updated

        try:
            previous_checksum = entropy.tools.get_hash_from_md5file(
                old_package_checksum)
        except (OSError, IOError) as err:
            if err.errno != errno.ENOENT:
                raise
            previous_checksum = None

        checksum = entropy.tools.get_hash_from_md5file(
            package_checksum)

        if (checksum == previous_checksum) and (
                previous_checksum is not None) and not force:
            return 0, updated

        status =  self._generic_download(self._url, package)
        if not status:
            txt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("unable to download advisories, sorry")),
            )
            self._entropy.output(
                txt,
                importance = 2,
                level = "error",
                header = red("   ## ")
            )
            return 1, updated

        txt = "%s: %s %s" % (
            bold(_("Security Advisories")),
            blue(_("Verifying checksum")),
            red("..."),
        )
        self._entropy.output(
            txt,
            importance = 1,
            level = "info",
            header = red("   # "),
            back = True
        )

        checksum = entropy.tools.get_hash_from_md5file(
            package_checksum)
        if checksum != previous_checksum:
            updated = True

        md5res = entropy.tools.compare_md5(package, checksum)
        if md5res:
            txt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkgreen(_("verification successful")),
            )
            self._entropy.output(
                txt,
                importance = 1,
                level = "info",
                header = red("   # ")
            )
        else:
            txt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("checksum verification failed, sorry")),
            )
            self._entropy.output(
                txt,
                importance = 2,
                level = "error",
                header = red("   ## ")
            )
            return 5, updated

        # download GPG key and package signature in a row
        # env hook, disable GPG check
        if self._gpg_enabled:
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
                    txt = "%s: %s." % (
                        bold(_("Security Advisories")),
                        purple(_("GPG service not available")),
                    )
                    self._entropy.output(
                        txt,
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
            extract_path = self._dir,
            catch_empty = True
        )

        # update mtime and atime of the directory as a way to invalidate
        # previous cached data. 1sec timestamp granularity of ext3 should
        # be enough anyway. This is much faster than md5summing all the xmls.
        t = time.time()
        os.utime(self._dir, (t, t))

        if status != 0:
            txt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("digest verification failed, try again later")),
            )
            self._entropy.output(
                txt,
                importance = 2,
                level = "error",
                header = red("   ## ")
            )
            return 6, updated

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
