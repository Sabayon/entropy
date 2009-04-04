# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

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

import os
import shutil
from entropy.exceptions import *
from entropy.const import etpConst, etpCache, etpUi, const_setup_perms
from entropy.i18n import _
from outputTools import blue, bold, red, darkgreen, darkred

class SecurityInterface:

    """
    ~~ GIVES YOU WINGS ~~
    """

    # thanks to Gentoo "gentoolkit" package, License below:

    # This program is licensed under the GPL, version 2

    # WARNING: this code is only tested by a few people and should NOT be used
    # on production systems at this stage. There are possible security holes and probably
    # bugs in this code. If you test it please report ANY success or failure to
    # me (genone@gentoo.org).

    # The following planned features are currently on hold:
    # - getting GLSAs from http/ftp servers (not really useful without the fixed ebuilds)
    # - GPG signing/verification (until key policy is clear)

    import entropy.tools as entropyTools
    def __init__(self, EquoInstance):

        # disabled for now
        from entropy.client.interfaces import Client
        if not isinstance(EquoInstance,Client):
            mytxt = _("A valid Client interface instance is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        self.Entropy = EquoInstance
        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()
        self.lastfetch = None
        self.previous_checksum = "0"
        self.advisories_changed = None
        self.adv_metadata = None
        self.affected_atoms = None

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

        self.unpackdir = os.path.join(etpConst['entropyunpackdir'],"security-"+str(self.entropyTools.get_random_number()))
        self.security_url = etpConst['securityurl']
        self.unpacked_package = os.path.join(self.unpackdir,"glsa_package")
        self.security_url_checksum = etpConst['securityurl']+etpConst['packagesmd5fileext']
        self.download_package = os.path.join(self.unpackdir,os.path.basename(etpConst['securityurl']))
        self.download_package_checksum = self.download_package+etpConst['packagesmd5fileext']
        self.old_download_package_checksum = os.path.join(etpConst['dumpstoragedir'],os.path.basename(etpConst['securityurl']))+etpConst['packagesmd5fileext']

        self.security_package = os.path.join(etpConst['securitydir'],os.path.basename(etpConst['securityurl']))
        self.security_package_checksum = self.security_package+etpConst['packagesmd5fileext']

        try:
            if os.path.isfile(etpConst['securitydir']) or os.path.islink(etpConst['securitydir']):
                os.remove(etpConst['securitydir'])
            if not os.path.isdir(etpConst['securitydir']):
                os.makedirs(etpConst['securitydir'],0775)
        except OSError:
            pass
        const_setup_perms(etpConst['securitydir'],etpConst['entropygid'])

        if os.path.isfile(self.old_download_package_checksum):
            f = open(self.old_download_package_checksum)
            try:
                self.previous_checksum = f.readline().strip().split()[0]
            except:
                pass
            f.close()

    def __prepare_unpack(self):

        if os.path.isfile(self.unpackdir) or os.path.islink(self.unpackdir):
            os.remove(self.unpackdir)
        if os.path.isdir(self.unpackdir):
            shutil.rmtree(self.unpackdir,True)
            try:
                os.rmdir(self.unpackdir)
            except OSError:
                pass
        os.makedirs(self.unpackdir,0775)
        const_setup_perms(self.unpackdir,etpConst['entropygid'])

    def __download_glsa_package(self):
        return self.__generic_download(self.security_url, self.download_package)

    def __download_glsa_package_checksum(self):
        return self.__generic_download(self.security_url_checksum, self.download_package_checksum, show_speed = False)

    def __generic_download(self, url, save_to, show_speed = True):
        fetchConn = self.Entropy.urlFetcher(url, save_to, resume = False, show_speed = show_speed)
        fetchConn.progress = self.Entropy.progress
        rc = fetchConn.download()
        del fetchConn
        if rc in ("-1","-2","-3","-4"):
            return False
        # setup permissions
        self.Entropy.setup_default_file_perms(save_to)
        return True

    def __verify_checksum(self):

        # read checksum
        if not os.path.isfile(self.download_package_checksum) or not os.access(self.download_package_checksum,os.R_OK):
            return 1

        f = open(self.download_package_checksum)
        try:
            checksum = f.readline().strip().split()[0]
            f.close()
        except:
            return 2

        if checksum == self.previous_checksum:
            self.advisories_changed = False
        else:
            self.advisories_changed = True
        md5res = self.entropyTools.compare_md5(self.download_package,checksum)
        if not md5res:
            return 3
        return 0

    def __unpack_advisories(self):
        rc = self.entropyTools.uncompress_tar_bz2(
            self.download_package,
            self.unpacked_package,
            catchEmpty = True
        )
        const_setup_perms(self.unpacked_package,etpConst['entropygid'])
        return rc

    def __clear_previous_advisories(self):
        if os.listdir(etpConst['securitydir']):
            shutil.rmtree(etpConst['securitydir'],True)
            if not os.path.isdir(etpConst['securitydir']):
                os.makedirs(etpConst['securitydir'],0775)
            const_setup_perms(self.unpackdir,etpConst['entropygid'])

    def __put_advisories_in_place(self):
        for advfile in os.listdir(self.unpacked_package):
            from_file = os.path.join(self.unpacked_package,advfile)
            to_file = os.path.join(etpConst['securitydir'],advfile)
            shutil.move(from_file,to_file)

    def __cleanup_garbage(self):
        shutil.rmtree(self.unpackdir,True)

    def clear(self, xcache = False):
        self.adv_metadata = None
        if xcache:
            self.Entropy.clear_dump_cache(etpCache['advisories'])

    def get_advisories_cache(self):

        if self.adv_metadata != None:
            return self.adv_metadata

        if self.Entropy.xcache:
            dir_checksum = self.entropyTools.md5sum_directory(etpConst['securitydir'])
            c_hash = "%s%s" % (etpCache['advisories'],hash("%s|%s|%s" % (hash(etpConst['branch']),hash(dir_checksum),hash(etpConst['systemroot']),)),)
            adv_metadata = self.Cacher.pop(c_hash)
            if adv_metadata != None:
                self.adv_metadata = adv_metadata.copy()
                return self.adv_metadata

    def set_advisories_cache(self, adv_metadata):
        if self.Entropy.xcache:
            dir_checksum = self.entropyTools.md5sum_directory(etpConst['securitydir'])
            c_hash = "%s%s" % (etpCache['advisories'],hash("%s|%s|%s" % (hash(etpConst['branch']),hash(dir_checksum),hash(etpConst['systemroot']),)),)
            self.Cacher.push(c_hash,adv_metadata)

    def get_advisories_list(self):
        if not self.check_advisories_availability():
            return []
        xmls = os.listdir(etpConst['securitydir'])
        xmls = sorted([x for x in xmls if x.endswith(".xml") and x.startswith("glsa-")])
        return xmls

    def get_advisories_metadata(self):

        cached = self.get_advisories_cache()
        if cached != None:
            return cached

        adv_metadata = {}
        xmls = self.get_advisories_list()
        maxlen = len(xmls)
        count = 0
        for xml in xmls:

            count += 1
            if not etpUi['quiet']: self.Entropy.updateProgress(":: "+str(round((float(count)/maxlen)*100,1))+"% ::", importance = 0, type = "info", back = True)

            xml_metadata = None
            exc_string = ""
            exc_err = ""
            try:
                xml_metadata = self.get_xml_metadata(xml)
            except KeyboardInterrupt:
                return {}
            except Exception, e:
                exc_string = str(Exception)
                exc_err = str(e)
            if xml_metadata == None:
                more_info = ""
                if exc_string:
                    mytxt = _("Error")
                    more_info = " %s: %s: %s" % (mytxt,exc_string,exc_err,)
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

    # this function filters advisories for packages that aren't
    # in the repositories. Note: only keys will be matched
    def filter_advisories(self, adv_metadata):
        keys = adv_metadata.keys()
        for key in keys:
            valid = True
            if adv_metadata[key]['affected']:
                affected = adv_metadata[key]['affected']
                affected_keys = affected.keys()
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
                        pass
                try:
                    if not adv_metadata[key]['affected']:
                        del adv_metadata[key]
                except KeyError:
                    pass

        return adv_metadata

    def is_affected(self, adv_key, adv_data = {}):
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
            # XXX: does multimatch work correctly?
            for atom in unaff_atoms:
                matches = self.Entropy.clientDbconn.atomMatch(atom, multiMatch = True)
                if matches[1] == 0:
                    for idpackage in matches[0]:
                        unaffected_atoms.add((idpackage,0))

            for atom in vul_atoms:
                match = self.Entropy.clientDbconn.atomMatch(atom)
                if (match[0] != -1) and (match not in unaffected_atoms):
                    if self.affected_atoms == None:
                        self.affected_atoms = set()
                    self.affected_atoms.add(atom)
                    return True
        return False

    def get_vulnerabilities(self):
        return self.get_affection()

    def get_fixed_vulnerabilities(self):
        return self.get_affection(affected = False)

    # if not affected: not affected packages will be returned
    # if affected: affected packages will be returned
    def get_affection(self, affected = True):
        adv_data = self.get_advisories_metadata()
        adv_data_keys = adv_data.keys()
        valid_keys = set()
        for adv in adv_data_keys:
            is_affected = self.is_affected(adv,adv_data)
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
            for key in adv_data[adv]['affected'].keys():
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
        adv_data = self.get_advisories_metadata()
        adv_data_keys = adv_data.keys()
        del adv_data
        self.affected_atoms = set()
        for key in adv_data_keys:
            self.is_affected(key)
        return self.affected_atoms

    def get_xml_metadata(self, xmlfilename):
        xml_data = {}
        xmlfile = os.path.join(etpConst['securitydir'],xmlfilename)
        try:
            xmldoc = self.minidom.parse(xmlfile)
        except:
            return None

        # get base data
        glsa_tree = xmldoc.getElementsByTagName("glsa")[0]
        glsa_product = glsa_tree.getElementsByTagName("product")[0]
        if glsa_product.getAttribute("type") != "ebuild":
            return {}

        glsa_id = glsa_tree.getAttribute("id")
        glsa_title = glsa_tree.getElementsByTagName("title")[0].firstChild.data
        glsa_synopsis = glsa_tree.getElementsByTagName("synopsis")[0].firstChild.data
        glsa_announced = glsa_tree.getElementsByTagName("announced")[0].firstChild.data
        glsa_revised = glsa_tree.getElementsByTagName("revised")[0].firstChild.data

        xml_data['filename'] = xmlfilename
        xml_data['url'] = "http://www.gentoo.org/security/en/glsa/%s" % (xmlfilename,)
        xml_data['title'] = glsa_title.strip()
        xml_data['synopsis'] = glsa_synopsis.strip()
        xml_data['announced'] = glsa_announced.strip()
        xml_data['revised'] = glsa_revised.strip()
        xml_data['bugs'] = ["https://bugs.gentoo.org/show_bug.cgi?id="+x.firstChild.data.strip() for x in glsa_tree.getElementsByTagName("bug")]
        xml_data['access'] = ""
        try:
            xml_data['access'] = glsa_tree.getElementsByTagName("access")[0].firstChild.data.strip()
        except IndexError:
            pass

        # references
        references = glsa_tree.getElementsByTagName("references")[0]
        xml_data['references'] = [x.getAttribute("link").strip() for x in references.getElementsByTagName("uri")]

        try:
            xml_data['description'] = ""
            xml_data['description_items'] = []
            desc = glsa_tree.getElementsByTagName("description")[0].getElementsByTagName("p")[0].firstChild.data.strip()
            xml_data['description'] = desc
            items = glsa_tree.getElementsByTagName("description")[0].getElementsByTagName("ul")
            for item in items:
                li_items = item.getElementsByTagName("li")
                for li_item in li_items:
                    xml_data['description_items'].append(' '.join([x.strip() for x in li_item.firstChild.data.strip().split("\n")]))
        except IndexError:
            xml_data['description'] = ""
            xml_data['description_items'] = []
        try:
            workaround = glsa_tree.getElementsByTagName("workaround")[0]
            xml_data['workaround'] = workaround.getElementsByTagName("p")[0].firstChild.data.strip()
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
            xml_data['impact'] = impact.getElementsByTagName("p")[0].firstChild.data.strip()
        except IndexError:
            xml_data['impact'] = ""
        xml_data['impacttype'] = glsa_tree.getElementsByTagName("impact")[0].getAttribute("type").strip()

        try:
            background = glsa_tree.getElementsByTagName("background")[0]
            xml_data['background'] = background.getElementsByTagName("p")[0].firstChild.data.strip()
        except IndexError:
            xml_data['background'] = ""

        # affection information
        affected = glsa_tree.getElementsByTagName("affected")[0]
        affected_packages = {}
        # we will then filter affected_packages using repositories information
        # if not affected_packages: advisory will be dropped
        for p in affected.getElementsByTagName("package"):
            name = p.getAttribute("name")
            if not affected_packages.has_key(name):
                affected_packages[name] = []

            pdata = {}
            pdata["arch"] = p.getAttribute("arch").strip()
            pdata["auto"] = (p.getAttribute("auto") == "yes")
            pdata["vul_vers"] = [self.__make_version(v) for v in p.getElementsByTagName("vulnerable")]
            pdata["unaff_vers"] = [self.__make_version(v) for v in p.getElementsByTagName("unaffected")]
            pdata["vul_atoms"] = [self.__make_atom(name, v) for v in p.getElementsByTagName("vulnerable")]
            pdata["unaff_atoms"] = [self.__make_atom(name, v) for v in p.getElementsByTagName("unaffected")]
            affected_packages[name].append(pdata)
        xml_data['affected'] = affected_packages.copy()

        return {glsa_id: xml_data}

    def __make_version(self, vnode):
        """
        creates from the information in the I{versionNode} a 
        version string (format <op><version>).

        @type	vnode: xml.dom.Node
        @param	vnode: a <vulnerable> or <unaffected> Node that
                                                    contains the version information for this atom
        @rtype:		String
        @return:	the version string
        """
        return self.op_mappings[vnode.getAttribute("range")] + vnode.firstChild.data.strip()

    def __make_atom(self, pkgname, vnode):
        """
        creates from the given package name and information in the 
        I{versionNode} a (syntactical) valid portage atom.

        @type	pkgname: String
        @param	pkgname: the name of the package for this atom
        @type	vnode: xml.dom.Node
        @param	vnode: a <vulnerable> or <unaffected> Node that
                                                    contains the version information for this atom
        @rtype:		String
        @return:	the portage atom
        """
        return str(self.op_mappings[vnode.getAttribute("range")] + pkgname + "-" + vnode.firstChild.data.strip())

    def check_advisories_availability(self):
        if not os.path.lexists(etpConst['securitydir']):
            return False
        if not os.path.isdir(etpConst['securitydir']):
            return False
        else:
            return True
        return False

    def fetch_advisories(self, do_cache = True):

        mytxt = "%s: %s" % (bold(_("Security Advisories")),blue(_("testing service connection")),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ "),
            footer = red(" ...")
        )

        mytxt = "%s: %s %s" % (bold(_("Security Advisories")),blue(_("getting latest GLSAs")),red("..."),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )

        gave_up = self.Entropy.lock_check(self.Entropy._resources_run_check_lock)
        if gave_up:
            return 7

        locked = self.Entropy.application_lock_check()
        if locked:
            self.Entropy._resources_run_remove_lock()
            return 4

        # lock
        self.Entropy._resources_run_create_lock()
        try:
            rc = self.run_fetch()
        except:
            self.Entropy._resources_run_remove_lock()
            raise
        if rc != 0: return rc

        self.Entropy._resources_run_remove_lock()

        if self.advisories_changed:
            advtext = "%s: %s" % (bold(_("Security Advisories")),darkgreen(_("updated successfully")),)
        else:
            advtext = "%s: %s" % (bold(_("Security Advisories")),darkgreen(_("already up to date")),)

        if do_cache and self.Entropy.xcache:
            self.get_advisories_metadata()
        self.Entropy.updateProgress(
            advtext,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )

        return 0

    def run_fetch(self):
        # prepare directories
        self.__prepare_unpack()

        # download package
        status = self.__download_glsa_package()
        self.lastfetch = status
        if not status:
            mytxt = "%s: %s." % (bold(_("Security Advisories")),darkred(_("unable to download the package, sorry")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy._resources_run_remove_lock()
            return 1

        mytxt = "%s: %s %s" % (bold(_("Security Advisories")),blue(_("Verifying checksum")),red("..."),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   # "),
            back = True
        )

        # download digest
        status = self.__download_glsa_package_checksum()
        if not status:
            mytxt = "%s: %s." % (bold(_("Security Advisories")),darkred(_("cannot download the checksum, sorry")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy._resources_run_remove_lock()
            return 2

        # verify digest
        status = self.__verify_checksum()

        if status == 1:
            mytxt = "%s: %s." % (bold(_("Security Advisories")),darkred(_("cannot open packages, sorry")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy._resources_run_remove_lock()
            return 3
        elif status == 2:
            mytxt = "%s: %s." % (bold(_("Security Advisories")),darkred(_("cannot read the checksum, sorry")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy._resources_run_remove_lock()
            return 4
        elif status == 3:
            mytxt = "%s: %s." % (bold(_("Security Advisories")),darkred(_("digest verification failed, sorry")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy._resources_run_remove_lock()
            return 5
        elif status == 0:
            mytxt = "%s: %s." % (bold(_("Security Advisories")),darkgreen(_("verification Successful")),)
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
        if os.path.isfile(self.download_package_checksum) and os.path.isdir(etpConst['dumpstoragedir']):
            if os.path.isfile(self.old_download_package_checksum):
                os.remove(self.old_download_package_checksum)
            shutil.copy2(self.download_package_checksum,self.old_download_package_checksum)
            self.Entropy.setup_default_file_perms(self.old_download_package_checksum)

        # now unpack in place
        status = self.__unpack_advisories()
        if status != 0:
            mytxt = "%s: %s." % (bold(_("Security Advisories")),darkred(_("digest verification failed, try again later")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 2,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy._resources_run_remove_lock()
            return 6

        mytxt = "%s: %s %s" % (bold(_("Security Advisories")),blue(_("installing")),red("..."),)
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