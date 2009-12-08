# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework Security module}.

    This module contains Entropy GLSA-based Security interfaces.
    

"""
import os
import shutil
from entropy.exceptions import IncorrectParameter, InvalidData
from entropy.const import etpConst, etpCache, etpUi, const_setup_perms
from entropy.i18n import _
from entropy.output import blue, bold, red, darkgreen, darkred

class System:

    """
    ~~ GIVES YOU WINGS ~~
    """

    """
    @note: thanks to Gentoo "gentoolkit" package, License below:
    @note:    This program is licensed under the GPL, version 2

    @note: WARNING: this code is not intended to replace any Security mechanism,
    @note: but it's just a way to handle Gentoo GLSAs.
    @note: There are possible security holes and probably bugs in this code.

    This class implements the Entropy packages Security framework.
    It can be used to retrieve security advisories, get information
    about unapplied advisories, etc.

    """

    import entropy.tools as entropyTools
    def __init__(self, entropy_client_instance):

        """
        Instance constructor.

        @param entropy_client_instance: a valid entropy.client.interfaces.Client
            instance
        @type entropy_client_instance: entropy.client.interfaces.Client instance
        """

        # disabled for now
        from entropy.client.interfaces import Client
        if not isinstance(entropy_client_instance, Client):
            mytxt = _("A valid Client interface instance is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        self.Entropy = entropy_client_instance
        from entropy.cache import EntropyCacher
        self.__cacher = EntropyCacher()
        from entropy.core.settings.base import SystemSettings
        self.SystemSettings = SystemSettings()
        self.lastfetch = None
        self.previous_checksum = "0"
        self.advisories_changed = None
        self.adv_metadata = None
        self.affected_atoms = set()

        from xml.dom import minidom
        self.minidom = minidom

        self.op_mappings = {
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

        security_url = \
            self.SystemSettings['repositories']['security_advisories_url']
        security_file = os.path.basename(security_url)
        md5_ext = etpConst['packagesmd5fileext']

        self.unpackdir = os.path.join(etpConst['entropyunpackdir'],
            "security-%s" % (self.entropyTools.get_random_number(),))
        self.security_url = security_url
        self.unpacked_package = os.path.join(self.unpackdir, "glsa_package")
        self.security_url_checksum = security_url + md5_ext

        self.download_package = os.path.join(self.unpackdir, security_file)
        self.download_package_checksum = self.download_package + md5_ext
        self.old_download_package_checksum = os.path.join(
            etpConst['dumpstoragedir'], os.path.basename(security_url)
        ) + md5_ext

        self.security_package = os.path.join(etpConst['securitydir'],
            os.path.basename(security_url))
        self.security_package_checksum = self.security_package + md5_ext

        try:

            if os.path.isfile(etpConst['securitydir']) or \
                os.path.islink(etpConst['securitydir']):
                os.remove(etpConst['securitydir'])

            if not os.path.isdir(etpConst['securitydir']):
                os.makedirs(etpConst['securitydir'], 0o775)

        except OSError:
            pass
        const_setup_perms(etpConst['securitydir'], etpConst['entropygid'])

        if os.access(self.old_download_package_checksum, os.R_OK) and \
            os.path.isfile(self.old_download_package_checksum):

            f_down = open(self.old_download_package_checksum)
            try:
                self.previous_checksum = f_down.readline().strip().split()[0]
            except (IndexError, OSError, IOError,):
                pass
            f_down.close()

    def __prepare_unpack(self):
        """
        Prepare GLSAs unpack directory and its permissions.
        """
        if os.path.isfile(self.unpackdir) or os.path.islink(self.unpackdir):
            os.remove(self.unpackdir)

        if os.path.isdir(self.unpackdir):
            shutil.rmtree(self.unpackdir, True)
            try:
                os.rmdir(self.unpackdir)
            except OSError:
                pass

        os.makedirs(self.unpackdir, 0o775)
        const_setup_perms(self.unpackdir, etpConst['entropygid'])

    def __download_glsa_package(self):
        """
        Download GLSA compressed package from a trusted source.
        """
        return self.__generic_download(self.security_url, self.download_package)

    def __download_glsa_package_cksum(self):
        """
        Download GLSA compressed package checksum (md5) from a trusted source.
        """
        return self.__generic_download(self.security_url_checksum,
            self.download_package_checksum, show_speed = False)

    def __generic_download(self, url, save_to, show_speed = True):
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
        fetcher = self.Entropy.urlFetcher(url, save_to, resume = False,
            show_speed = show_speed)
        fetcher.progress = self.Entropy.progress
        rc_fetch = fetcher.download()
        del fetcher
        if rc_fetch in ("-1", "-2", "-3", "-4"):
            return False
        # setup permissions
        self.Entropy.setup_default_file_perms(save_to)
        return True

    def __verify_checksum(self):
        """
        Verify downloaded GLSA checksum against downloaded GLSA package.
        """
        # read checksum
        if not os.path.isfile(self.download_package_checksum) or \
            not os.access(self.download_package_checksum, os.R_OK):
            return 1

        f_down = open(self.download_package_checksum)
        read_err = False
        try:
            checksum = f_down.readline().strip().split()[0]
        except (OSError, IOError, IndexError,):
            read_err = True

        f_down.close()
        if read_err:
            return 2

        self.advisories_changed = True
        if checksum == self.previous_checksum:
            self.advisories_changed = False

        md5res = self.entropyTools.compare_md5(self.download_package, checksum)
        if not md5res:
            return 3
        return 0

    def __unpack_advisories(self):
        """
        Unpack downloaded GLSA package containing GLSA advisories.
        """
        rc_unpack = self.entropyTools.uncompress_tar_bz2(
            self.download_package,
            self.unpacked_package,
            catchEmpty = True
        )
        const_setup_perms(self.unpacked_package, etpConst['entropygid'])
        return rc_unpack

    def __clear_previous_advisories(self):
        """
        Remove previously installed GLSA advisories.
        """
        if os.listdir(etpConst['securitydir']):
            shutil.rmtree(etpConst['securitydir'], True)
            if not os.path.isdir(etpConst['securitydir']):
                os.makedirs(etpConst['securitydir'], 0o775)
            const_setup_perms(self.unpackdir, etpConst['entropygid'])

    def __put_advisories_in_place(self):
        """
        Place unpacked advisories in place (into etpConst['securitydir']).
        """
        for advfile in os.listdir(self.unpacked_package):
            from_file = os.path.join(self.unpacked_package, advfile)
            to_file = os.path.join(etpConst['securitydir'], advfile)
            try:
                os.rename(from_file, to_file)
            except OSError:
                shutil.move(from_file, to_file)

    def __cleanup_garbage(self):
        """
        Remove GLSA unpack directory.
        """
        shutil.rmtree(self.unpackdir, True)

    def clear(self, xcache = False):
        """
        Clear instance cache (RAM and on-disk).

        @keyword xcache: also remove Entropy on-disk cache if True
        @type xcache: bool
        """
        self.adv_metadata = None
        if xcache:
            self.Entropy.clear_dump_cache(etpCache['advisories'])

    def get_advisories_cache(self):
        """
        Return cached advisories information metadata. It first tries to load
        them from RAM and, in case of failure, it tries to gather the info
        from disk, using EntropyCacher.
        """
        if self.adv_metadata != None:
            return self.adv_metadata

        if self.Entropy.xcache:
            dir_checksum = self.entropyTools.md5sum_directory(
                etpConst['securitydir'])
            c_hash = "%s%s" % (
                etpCache['advisories'], hash("%s|%s|%s" % (
                    hash(self.SystemSettings['repositories']['branch']),
                    hash(dir_checksum),
                    hash(etpConst['systemroot']),
                )),
            )
            adv_metadata = self.__cacher.pop(c_hash)
            if adv_metadata != None:
                self.adv_metadata = adv_metadata.copy()
                return self.adv_metadata

    def set_advisories_cache(self, adv_metadata):
        """
        Set advisories information metadata cache.

        @param adv_metadata: advisories metadata to store
        @type adv_metadata: dict
        """
        if self.Entropy.xcache:
            dir_checksum = self.entropyTools.md5sum_directory(
                etpConst['securitydir'])
            c_hash = "%s%s" % (
                etpCache['advisories'], hash("%s|%s|%s" % (
                    hash(self.SystemSettings['repositories']['branch']),
                    hash(dir_checksum),
                    hash(etpConst['systemroot']),
                )),
            )
            self.__cacher.push(c_hash, adv_metadata)

    def _get_advisories_list(self):
        """
        Return a list of advisory files. Internal method.
        """
        if not self.check_advisories_availability():
            return []
        xmls = os.listdir(etpConst['securitydir'])
        xmls = sorted([x for x in xmls if x.endswith(".xml") and \
            x.startswith("glsa-")])
        return xmls

    def get_advisories_metadata(self):
        """
        Get security advisories metadata.

        @return: advisories metadata
        @rtype: dict
        """
        cached = self.get_advisories_cache()
        if cached != None:
            return cached

        adv_metadata = {}
        xmls = self._get_advisories_list()
        maxlen = len(xmls)
        count = 0
        for xml in xmls:

            count += 1
            if not etpUi['quiet']:
                self.Entropy.updateProgress(":: " + \
                    str(round((float(count)/maxlen)*100, 1)) + "% ::",
                    importance = 0, type = "info", back = True)

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
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = red(" !!! ")
                )
                continue
            elif not xml_metadata:
                continue
            adv_metadata.update(xml_metadata)

        adv_metadata = self.filter_advisories(adv_metadata)
        self.set_advisories_cache(adv_metadata)
        self.adv_metadata = adv_metadata.copy()
        return adv_metadata

    def filter_advisories(self, adv_metadata):
        """
        This function filters advisories metadata dict removing non-applicable
        ones.

        @param adv_metadata: security advisories metadata dict
        @type adv_metadata: dict
        @return: filtered security advisories metadata
        @rtype: dict
        """
        keys = list(adv_metadata.keys())
        for key in keys:
            valid = True
            if adv_metadata[key]['affected']:
                affected = adv_metadata[key]['affected']
                affected_keys = list(affected.keys())
                valid = False
                skipping_keys = set()
                for a_key in affected_keys:
                    match = self.Entropy.atom_match(a_key)
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
                matches = self.Entropy.clientDbconn.atomMatch(atom,
                    multiMatch = True)
                for idpackage in matches[0]:
                    unaffected_atoms.add((idpackage, 0))

            for atom in vul_atoms:
                match = self.Entropy.clientDbconn.atomMatch(atom)
                if (match[0] != -1) and (match not in unaffected_atoms):
                    self.affected_atoms.add(atom)
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
                    if atom in self.affected_atoms:
                        applicable = False
                        break
                if applicable == affected:
                    del adv_data[adv]['affected'][key]
        return adv_data

    def get_affected_atoms(self):
        """
        Return a list of package atoms affected by vulnerabilities.

        @return: list (set) of package atoms affected by vulnerabilities
        @rtype: set
        """
        adv_data = self.get_advisories_metadata()
        adv_data_keys = list(adv_data.keys())
        del adv_data
        self.affected_atoms.clear()
        for key in adv_data_keys:
            self.is_affected(key)
        return self.affected_atoms

    def __get_xml_metadata(self, xmlfilename):
        """
        Parses a Gentoo GLSA XML file extracting advisory metadata.

        @param xmlfilename: GLSA filename
        @type xmlfilename: string
        @return: advisory metadata extracted
        @rtype: dict
        """
        xml_data = {}
        xmlfile = os.path.join(etpConst['securitydir'], xmlfilename)
        try:
            xmldoc = self.minidom.parse(xmlfile)
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
        return self.op_mappings[vnode.getAttribute("range")] + \
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
        return str(self.op_mappings[vnode.getAttribute("range")] + pkgname + \
            "-" + vnode.firstChild.data.strip())

    def check_advisories_availability(self):
        """
        Return whether security advisories are available.

        @return: availability
        @rtype: bool
        """
        if not os.path.lexists(etpConst['securitydir']):
            return False
        if not os.path.isdir(etpConst['securitydir']):
            return False
        else:
            return True
        return False

    def fetch_advisories(self, do_cache = True):
        """
        This is the service method for remotely fetch advisories metadata.

        @keyword do_cache: generates advisories cache
        @type do_cache: bool
        @return: execution status (0 means all file)
        @rtype: int
        """
        mytxt = "%s: %s" % (
            bold(_("Security Advisories")),
            blue(_("testing service connection")),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ "),
            footer = red(" ...")
        )

        mytxt = "%s: %s %s" % (
            bold(_("Security Advisories")),
            blue(_("getting latest GLSAs")),
            red("..."),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )

        gave_up = self.Entropy.lock_check(
            self.Entropy.resources_check_lock)
        if gave_up:
            return 7

        locked = self.Entropy.application_lock_check()
        if locked:
            return 4

        # lock
        acquired = self.Entropy.resources_create_lock()
        if not acquired:
            return 4 # app locked during lock acquire
        try:
            rc_lock = self.__run_fetch()
        except:
            self.Entropy.resources_remove_lock()
            raise
        if rc_lock != 0:
            return rc_lock

        self.Entropy.resources_remove_lock()

        if self.advisories_changed:
            advtext = "%s: %s" % (
                bold(_("Security Advisories")),
                darkgreen(_("updated successfully")),
            )
        else:
            advtext = "%s: %s" % (
                bold(_("Security Advisories")),
                darkgreen(_("already up to date")),
            )

        if do_cache and self.Entropy.xcache:
            self.get_advisories_metadata()
        self.Entropy.updateProgress(
            advtext,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )

        return 0

    def __run_fetch(self):
        # prepare directories
        self.__prepare_unpack()

        # download package
        status = self.__download_glsa_package()
        self.lastfetch = status
        if not status:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("unable to download the package, sorry")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy.resources_remove_lock()
            return 1

        mytxt = "%s: %s %s" % (
            bold(_("Security Advisories")),
            blue(_("Verifying checksum")),
            red("..."),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   # "),
            back = True
        )

        # download digest
        status = self.__download_glsa_package_cksum()
        if not status:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("cannot download the checksum, sorry")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy.resources_remove_lock()
            return 2

        # verify digest
        status = self.__verify_checksum()

        if status == 1:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("cannot open packages, sorry")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy.resources_remove_lock()
            return 3
        elif status == 2:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("cannot read the checksum, sorry")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy.resources_remove_lock()
            return 4
        elif status == 3:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("digest verification failed, sorry")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy.resources_remove_lock()
            return 5
        elif status == 0:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkgreen(_("verification Successful")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red("   # ")
            )
        else:
            mytxt = _("Return status not valid")
            raise InvalidData("InvalidData: %s." % (mytxt,))

        # save downloaded md5
        if os.path.isfile(self.download_package_checksum) and \
            os.path.isdir(etpConst['dumpstoragedir']):

            if os.path.isfile(self.old_download_package_checksum):
                os.remove(self.old_download_package_checksum)
            shutil.copy2(self.download_package_checksum,
                self.old_download_package_checksum)
            self.Entropy.setup_default_file_perms(
                self.old_download_package_checksum)

        # now unpack in place
        status = self.__unpack_advisories()
        if status != 0:
            mytxt = "%s: %s." % (
                bold(_("Security Advisories")),
                darkred(_("digest verification failed, try again later")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy.resources_remove_lock()
            return 6

        mytxt = "%s: %s %s" % (
            bold(_("Security Advisories")),
            blue(_("installing")),
            red("..."),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   # ")
        )

        # clear previous
        self.__clear_previous_advisories()
        # copy over
        self.__put_advisories_in_place()
        # remove temp stuff
        self.__cleanup_garbage()
        return 0
