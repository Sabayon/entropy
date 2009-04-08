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
from __future__ import with_statement
import os
import shutil
from entropy.i18n import _
from entropy.const import *
from entropy.exceptions import *
from entropy.output import red, bold, brown

class ExtractorsMixin:

    def _extract_pkg_metadata_generate_extraction_dict(self):
        data = {
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
        }
        return data

    def _extract_pkg_metadata_content(self, content_file, package_path):

        pkg_content = {}

        if os.path.isfile(content_file):
            f = open(content_file,"r")
            content = f.readlines()
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

            _outcontent = set()
            for i in outcontent:
                i = list(i)
                datatype = i[1]
                _outcontent.add((i[0],i[1]))
            outcontent = sorted(_outcontent)
            for i in outcontent:
                pkg_content[i[0]] = i[1]

        else:

            # CONTENTS is not generated when a package is emerged with portage and the option -B
            # we have to unpack the tbz2 and generate content dict
            mytempdir = etpConst['packagestmpdir']+"/"+os.path.basename(package_path)+".inject"
            if os.path.isdir(mytempdir):
                shutil.rmtree(mytempdir)
            if not os.path.isdir(mytempdir):
                os.makedirs(mytempdir)

            self.entropyTools.uncompress_tar_bz2(package_path, extractPath = mytempdir, catchEmpty = True)
            for currentdir, subdirs, files in os.walk(mytempdir):
                pkg_content[currentdir[len(mytempdir):]] = "dir"
                for item in files:
                    item = currentdir+"/"+item
                    if os.path.islink(item):
                        pkg_content[item[len(mytempdir):]] = "sym"
                    else:
                        pkg_content[item[len(mytempdir):]] = "obj"

            # now remove
            shutil.rmtree(mytempdir,True)
            try: os.rmdir(mytempdir)
            except (OSError,): pass

        return pkg_content

    def _extract_pkg_metadata_needed(self, needed_file):

        pkg_needed = set()
        lines = []

        try:
            f = open(needed_file,"r")
            lines = [x.strip() for x in f.readlines() if x.strip()]
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

        return list(pkg_needed)

    def _extract_pkg_metadata_messages(self, log_dir, category, name, version, silent = False):

        pkg_messages = []

        if os.path.isdir(log_dir):

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
                    pkg_messages.append(message)

        elif not silent:

            mytxt = " %s, %s" % (_("not set"),_("have you configured make.conf properly?"),)
            self.updateProgress(
                red(log_dir)+mytxt,
                importance = 1,
                type = "warning",
                header = brown(" * ")
            )

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
                        pkg_licensedata[mylicense] = f.read()
                        f.close()

        return pkg_licensedata

    def _extract_pkg_metadata_mirror_links(self, Spm, sources_list):

        # =mirror://openoffice|link1|link2|link3
        pkg_links = []
        for i in sources_list:
            if i.startswith("mirror://"):
                # parse what mirror I need
                mirrorURI = i.split("/")[2]
                mirrorlist = Spm.get_third_party_mirrors(mirrorURI)
                pkg_links.append([mirrorURI,mirrorlist])
                # mirrorURI = openoffice and mirrorlist = [link1, link2, link3]

        return pkg_links

    def _extract_pkg_metadata_ebuild_entropy_tag(self, ebuild):
        search_tag = etpConst['spm']['ebuild_pkg_tag_var']
        ebuild_tag = ''
        f = open(ebuild,"r")
        tags = [x.strip() for x in f.readlines() if x.strip() and x.strip().startswith(search_tag)]
        f.close()
        if not tags: return ebuild_tag
        tag = tags[-1]
        tag = tag.split("=")[-1].strip('"').strip("'").strip()
        return tag

    # This function extracts all the info from a .tbz2 file and returns them
    def extract_pkg_metadata(self, package, etpBranch = None, silent = False,
        inject = False):

        if etpBranch == None:
            etpBranch = self.SystemSettings['repositories']['branch']

        data = {}
        info_package = bold(os.path.basename(package))+": "

        if not silent:
            self.updateProgress(
                red(info_package+_("Extracting package metadata")+" ..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )

        filepath = package
        tbz2File = package
        package = package.split(etpConst['packagesext'])[0]
        package = self.entropyTools.remove_entropy_revision(package)
        package = self.entropyTools.remove_tag(package)
        # remove entropy category
        if package.find(":") != -1:
            package = ':'.join(package.split(":")[1:])

        # pkgcat is always == "null" here
        pkgcat, pkgname, pkgver, pkgrev = self.entropyTools.catpkgsplit(os.path.basename(package))
        if pkgrev != "r0": pkgver += "-%s" % (pkgrev,)

        # Fill Package name and version
        data['name'] = pkgname
        data['version'] = pkgver
        data['digest'] = self.entropyTools.md5sum(tbz2File)
        data['signatures'] = {
            'sha1': self.entropyTools.sha1(tbz2File),
            'sha256': self.entropyTools.sha256(tbz2File),
            'sha512': self.entropyTools.sha512(tbz2File),
        }
        data['datecreation'] = str(self.entropyTools.get_file_unix_mtime(tbz2File))
        data['size'] = str(self.entropyTools.get_file_size(tbz2File))

        tbz2TmpDir = etpConst['packagestmpdir']+"/"+data['name']+"-"+data['version']+"/"
        if not os.path.isdir(tbz2TmpDir):
            if os.path.lexists(tbz2TmpDir):
                os.remove(tbz2TmpDir)
            os.makedirs(tbz2TmpDir)
        self.entropyTools.extract_xpak(tbz2File,tbz2TmpDir)

        data['injected'] = False
        if inject: data['injected'] = True
        data['branch'] = etpBranch

        portage_entries = self._extract_pkg_metadata_generate_extraction_dict()
        for item in portage_entries:
            value = ''
            try:
                f = open(os.path.join(tbz2TmpDir,portage_entries[item]['path']),"r")
                value = f.readline().strip()
                f.close()
            except IOError:
                if portage_entries[item]['critical']:
                    raise
            data[item] = value

        # setup vars
        data['eclasses'] = data['eclasses'].split()
        try:
            data['counter'] = int(data['counter'])
        except ValueError:
            data['counter'] = -2 # -2 values will be insterted as incremental negative values into the database
        data['keywords'] = [x.strip() for x in data['keywords'].split() if x.strip()]
        if not data['keywords']: data['keywords'].insert(0,"") # support for packages with no keywords
        needed_file = os.path.join(tbz2TmpDir,etpConst['spm']['xpak_entries']['needed'])
        data['needed'] = self._extract_pkg_metadata_needed(needed_file)
        content_file = os.path.join(tbz2TmpDir,etpConst['spm']['xpak_entries']['contents'])
        data['content'] = self._extract_pkg_metadata_content(content_file, filepath)
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
        ebuilds_in_path = [x for x in os.listdir(tbz2TmpDir) if x.endswith(".%s" % (file_ext,))]
        if not data['versiontag'] and ebuilds_in_path:
            # has the user specified a custom package tag inside the ebuild
            ebuild_path = os.path.join(tbz2TmpDir,ebuilds_in_path[0])
            data['versiontag'] = self._extract_pkg_metadata_ebuild_entropy_tag(ebuild_path)


        data['download'] = etpConst['packagesrelativepath'] + data['branch'] + "/"
        data['download'] += self.entropyTools.create_package_filename(data['category'], data['name'], data['version'], data['versiontag'])


        data['trigger'] = ""
        if os.path.isfile(etpConst['triggersdir']+"/"+data['category']+"/"+data['name']+"/"+etpConst['triggername']):
            f = open(etpConst['triggersdir']+"/"+data['category']+"/"+data['name']+"/"+etpConst['triggername'],"rb")
            data['trigger'] = f.read()
            f.close()

        Spm = self.Spm()

        # Get Spm ChangeLog
        pkgatom = "%s/%s-%s" % (data['category'],data['name'],data['version'],)
        try:
            data['changelog'] = Spm.get_package_changelog(pkgatom)
        except:
            data['changelog'] = None

        portage_metadata = Spm.calculate_dependencies(
            data['iuse'], data['use'], data['license'], data['depend'],
            data['rdepend'], data['pdepend'], data['provide'], data['sources']
        )

        data['provide'] = portage_metadata['PROVIDE'].split()
        data['license'] = portage_metadata['LICENSE']
        data['useflags'] = []
        for x in data['use'].split():
            if x.startswith("+"):
                x = x[1:]
            elif x.startswith("-"):
                x = x[1:]
            if (x in portage_metadata['USE']) or (x in portage_metadata['USE_MASK']):
                data['useflags'].append(x)
            else:
                data['useflags'].append("-"+x)
        data['sources'] = portage_metadata['SRC_URI'].split()
        data['dependencies'] = {}
        for x in portage_metadata['RDEPEND'].split():
            if x.startswith("!") or (x in ("(","||",")","")):
                continue
            data['dependencies'][x] = etpConst['spm']['(r)depend_id']
        for x in portage_metadata['PDEPEND'].split():
            if x.startswith("!") or (x in ("(","||",")","")):
                continue
            data['dependencies'][x] = etpConst['spm']['pdepend_id']
        data['conflicts'] = [x[1:] for x in portage_metadata['RDEPEND'].split()+portage_metadata['PDEPEND'].split() if x.startswith("!") and not x in ("(","||",")","")]

        if (kernelstuff) and (not kernelstuff_kernel):
            # add kname to the dependency
            data['dependencies']["=sys-kernel/linux-"+kname+"-"+kver+"~-1"] = etpConst['spm']['(r)depend_id']

        # Conflicting tagged packages support
        key = data['category']+"/"+data['name']
        confl_data = self.SystemSettings['conflicting_tagged_packages'].get(key)
        if confl_data != None:
            for conflict in confl_data: data['conflicts'].append(conflict)

        # Get License text if possible
        licenses_dir = os.path.join(Spm.get_spm_setting('PORTDIR'),'licenses')
        data['licensedata'] = self._extract_pkg_metadata_license_data(licenses_dir, data['license'])
        data['mirrorlinks'] = self._extract_pkg_metadata_mirror_links(Spm, data['sources'])

        # write only if it's a systempackage
        data['systempackage'] = False
        system_packages = [self.entropyTools.dep_getkey(x) for x in Spm.get_atoms_in_system()]
        if data['category']+"/"+data['name'] in system_packages:
            data['systempackage'] = True

        # write only if it's a systempackage
        protect, mask = Spm.get_config_protect_and_mask()
        data['config_protect'] = protect
        data['config_protect_mask'] = mask

        log_dir = etpConst['logdir']+"/elog"
        if not os.path.isdir(log_dir): os.makedirs(log_dir)
        data['messages'] = self._extract_pkg_metadata_messages(log_dir, data['category'], data['name'], data['version'], silent = silent)
        data['etpapi'] = etpConst['etpapi']

        # removing temporary directory
        shutil.rmtree(tbz2TmpDir,True)
        if os.path.isdir(tbz2TmpDir):
            try: os.remove(tbz2TmpDir)
            except OSError: pass

        if not silent:
            self.updateProgress(
                red(info_package+_("Package extraction complete")), importance = 0,
                type = "info", header = brown(" * "), back = True
            )
        return data


