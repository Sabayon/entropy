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
from entropy.exceptions import *
from entropyConstants import *

class Singleton(object):

    def __new__(cls, *args, **kwds):
        it = cls.__dict__.get("__it__")
        if it != None:
            try:
                ck_dst = it.is_destroyed
                if not callable(ck_dst): raise AttributeError
                destroyed = ck_dst()
            except AttributeError:
                destroyed = False
            if not destroyed:
                return it
        cls.__it__ = it = object.__new__(cls)
        it.init_singleton(*args, **kwds)
        return it

class SystemSettings(Singleton):

    import entropyTools
    def init_singleton(self, EquoInstance):

        self.__data = {}
        self.__is_destroyed = False
        # XXX disabled for now
        #if not isinstance(EquoInstance,EquoInterface):
        #    mytxt = _("A valid Equo instance or subclass is needed")
        #    raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        self.Entropy = EquoInstance

        self.etpSettingFiles = {
            'keywords': etpConst['confpackagesdir']+"/package.keywords", # keywording configuration files
            'unmask': etpConst['confpackagesdir']+"/package.unmask", # unmasking configuration files
            'mask': etpConst['confpackagesdir']+"/package.mask", # masking configuration files
            'license_mask': etpConst['confpackagesdir']+"/license.mask", # masking configuration files
            'repos_system_mask': {},
            'system_mask': etpConst['confpackagesdir']+"/system.mask",
            'repos_mask': {},
            'repos_license_whitelist': {},
            'system_package_sets': {},
            'conflicting_tagged_packages': {},
            'system_dirs': etpConst['confdir']+"/fsdirs.conf",
            'system_dirs_mask': etpConst['confdir']+"/fsdirsmask.conf",
        }

        ## XXX trunk support, for a while - exp. date 10/10/2009
        trunk_fsdirs_conf = "../conf/fsdirs.conf"
        trunk_fsdirsmask_conf = "../conf/fsdirsmask.conf"
        if os.path.isfile(trunk_fsdirs_conf):
            self.etpSettingFiles['system_dirs'] = trunk_fsdirs_conf
        if os.path.isfile(trunk_fsdirsmask_conf):
            self.etpSettingFiles['system_dirs_mask'] = trunk_fsdirsmask_conf

        self.etpMtimeFiles = {
            'keywords_mtime': etpConst['dumpstoragedir']+"/keywords.mtime",
            'unmask_mtime': etpConst['dumpstoragedir']+"/unmask.mtime",
            'mask_mtime': etpConst['dumpstoragedir']+"/mask.mtime",
            'license_mask_mtime': etpConst['dumpstoragedir']+"/license_mask.mtime",
            'system_mask_mtime': etpConst['dumpstoragedir']+"/system_mask.mtime",
            'repos_system_mask': {},
            'repos_mask': {},
            'repos_license_whitelist': {},
        }

        self.__persistent_settings = {
            'pkg_masking_reasons': {
                0: _('reason not available'),
                1: _('user package.mask'),
                2: _('system keywords'),
                3: _('user package.unmask'),
                4: _('user repo package.keywords (all packages)'),
                5: _('user repo package.keywords'),
                6: _('user package.keywords'),
                7: _('completely masked'),
                8: _('repository general packages.db.mask'),
                9: _('repository in branch packages.db.mask'), # FIXME: this has been removed
                10: _('user license.mask'),
                11: _('user live unmask'),
                12: _('user live mask'),
            },
            'pkg_masking_reference': {
                'reason_not_avail': 0,
                'user_package_mask': 1,
                'system_keyword': 2,
                'user_package_unmask': 3,
                'user_repo_package_keywords_all': 4,
                'user_repo_package_keywords': 5,
                'user_package_keywords': 6,
                'completely_masked': 7,
                'repository_packages_db_mask': 8,
                'repository_in_branch_pacakges_db_mask': 9,
                'user_license_mask': 10,
                'user_live_unmask': 11,
                'user_live_mask': 12,
            },
        }
        self.__scan()

    def destroy(self):
        self.__is_destroyed = True

    def __scan(self):

        self.__data.update(self.__parse())
        # merge universal keywords
        for x in self.__data['keywords']['universal']:
            etpConst['keywords'].add(x)

        # live package masking / unmasking
        self.__data.update(
            {
                'live_packagemasking': {
                    'unmask_matches': set(),
                    'mask_matches': set(),
                }
            }
        )

        # match installed packages of system_mask
        self.__data['repos_system_mask_installed'] = []
        self.__data['repos_system_mask_installed_keys'] = {}
        if self.Entropy.clientDbconn != None:
            while 1:
                try:
                    self.Entropy.clientDbconn.validateDatabase()
                except SystemDatabaseError:
                    break
                mc_cache = set()
                m_list = self.__data['repos_system_mask']+self.__data['system_mask']
                for atom in m_list:
                    m_ids,m_r = self.Entropy.clientDbconn.atomMatch(atom, multiMatch = True)
                    if m_r != 0: continue
                    mykey = self.entropyTools.dep_getkey(atom)
                    if mykey not in self.__data['repos_system_mask_installed_keys']:
                        self.__data['repos_system_mask_installed_keys'][mykey] = set()
                    for xm in m_ids:
                        if xm in mc_cache: continue
                        mc_cache.add(xm)
                        self.__data['repos_system_mask_installed'].append(xm)
                        self.__data['repos_system_mask_installed_keys'][mykey].add(xm)
                break

        # Live package masking
        self.__data.update(self.__persistent_settings)

    def __setitem__(self, mykey, myvalue):
        if self.__persistent_settings.has_key(mykey): # backup here too
            self.__persistent_settings[mykey] = myvalue
        self.__data[mykey] = myvalue

    def __getitem__(self, mykey):
        return self.__data[mykey]

    def __delitem__(self, mykey):
        del self.__data[mykey]

    def __iter__(self):
        return iter(self.__data)

    def __contains__(self, item):
        return item in self.__data

    def __cmp__(self, other):
        return cmp(self.__data,other)

    def __hash__(self):
        return hash(self.__data)

    def __len__(self):
        return len(self.__data)

    def get(self, mykey):
        return self.__data.get(mykey)

    def has_key(self, mykey):
        return self.__data.has_key(mykey)

    def copy(self):
        return self.__data.copy()

    def fromkeys(self, seq, val = None):
        return self.__data.fromkeys(seq, val)

    def items(self):
        return self.__data.items()

    def iteritems(self):
        return self.__data.iteritems()

    def iterkeys(self):
        return self.__data.iterkeys()

    def keys(self):
        return self.__data.keys()

    def pop(self, mykey, default = None):
        return self.__data.pop(mykey,default)

    def popitem(self):
        return self.__data.popitem()

    def setdefault(self, mykey, default = None):
        return self.__data.setdefault(mykey,default)

    def update(self, **kwargs):
        return self.__data.update(kwargs)

    def values(self):
        return self.__data.values()

    def clear(self):
        self.__data.clear()
        self.__scan()

    def __parse(self):

        # append repositories mask files
        # append repositories mtime files
        for repoid in etpRepositoriesOrder:
            maskpath = os.path.join(etpRepositories[repoid]['dbpath'],etpConst['etpdatabasemaskfile'])
            wlpath = os.path.join(etpRepositories[repoid]['dbpath'],etpConst['etpdatabaselicwhitelistfile'])
            sm_path = os.path.join(etpRepositories[repoid]['dbpath'],etpConst['etpdatabasesytemmaskfile'])
            ct_path = os.path.join(etpRepositories[repoid]['dbpath'],etpConst['etpdatabaseconflictingtaggedfile'])
            if os.path.isfile(maskpath) and os.access(maskpath,os.R_OK):
                self.etpSettingFiles['repos_mask'][repoid] = maskpath
                self.etpMtimeFiles['repos_mask'][repoid] = etpConst['dumpstoragedir']+"/repo_"+repoid+"_"+etpConst['etpdatabasemaskfile']+".mtime"
            if os.path.isfile(wlpath) and os.access(wlpath,os.R_OK):
                self.etpSettingFiles['repos_license_whitelist'][repoid] = wlpath
                self.etpMtimeFiles['repos_license_whitelist'][repoid] = etpConst['dumpstoragedir']+"/repo_"+repoid+"_"+etpConst['etpdatabaselicwhitelistfile']+".mtime"
            if os.path.isfile(sm_path) and os.access(sm_path,os.R_OK):
                self.etpSettingFiles['repos_system_mask'][repoid] = sm_path
                self.etpMtimeFiles['repos_system_mask'][repoid] = etpConst['dumpstoragedir']+"/repo_"+repoid+"_"+etpConst['etpdatabasesytemmaskfile']+".mtime"
            if os.path.isfile(ct_path) and os.access(ct_path,os.R_OK):
                self.etpSettingFiles['conflicting_tagged_packages'][repoid] = ct_path

        # user defined package sets
        sets_dir = etpConst['confsetsdir']
        if (os.path.isdir(sets_dir) and os.access(sets_dir,os.R_OK)):
            set_files = [x for x in os.listdir(sets_dir) if (os.path.isfile(os.path.join(sets_dir,x)) and os.access(os.path.join(sets_dir,x),os.R_OK))]
            for set_file in set_files:
                try:
                    set_file = str(set_file)
                except (UnicodeDecodeError,UnicodeEncodeError,):
                    continue
                self.etpSettingFiles['system_package_sets'][set_file] = os.path.join(sets_dir,set_file)

        data = {}
        for item in self.etpSettingFiles:
            myattr = '%s_parser' % (item,)
            if not hasattr(self,myattr): continue
            f = getattr(self,myattr)
            data[item] = f()
        return data


    '''
    parser of package.keywords file
    '''
    def keywords_parser(self):

        data = {
                'universal': set(),
                'packages': {},
                'repositories': {},
        }

        self.__validateEntropyCache(self.etpSettingFiles['keywords'],self.etpMtimeFiles['keywords_mtime'])
        content = [x.split() for x in self.__generic_parser(self.etpSettingFiles['keywords']) if len(x.split()) < 4]
        for keywordinfo in content:
            # skip wrong lines
            if len(keywordinfo) > 3: continue
            if len(keywordinfo) == 1: # inversal keywording, check if it's not repo=
                # repo=?
                if keywordinfo[0].startswith("repo="): continue
                #kinfo = keywordinfo[0]
                if keywordinfo[0] == "**": keywordinfo[0] = "" # convert into entropy format
                data['universal'].add(keywordinfo[0])
                continue # needed?
            if len(keywordinfo) in (2,3): # inversal keywording, check if it's not repo=
                # repo=?
                if keywordinfo[0].startswith("repo="): continue
                # add to repo?
                items = keywordinfo[1:]
                if keywordinfo[0] == "**": keywordinfo[0] = "" # convert into entropy format
                reponame = [x for x in items if x.startswith("repo=") and (len(x.split("=")) == 2)]
                if reponame:
                    reponame = reponame[0].split("=")[1]
                    if reponame not in data['repositories']:
                        data['repositories'][reponame] = {}
                    # repository unmask or package in repository unmask?
                    if keywordinfo[0] not in data['repositories'][reponame]:
                        data['repositories'][reponame][keywordinfo[0]] = set()
                    if len(items) == 1:
                        # repository unmask
                        data['repositories'][reponame][keywordinfo[0]].add('*')
                    else:
                        if "*" not in data['repositories'][reponame][keywordinfo[0]]:
                            item = [x for x in items if not x.startswith("repo=")]
                            data['repositories'][reponame][keywordinfo[0]].add(item[0])
                else:
                    # it's going to be a faulty line!!??
                    if len(items) == 2: # can't have two items and no repo=
                        continue
                    # add keyword to packages
                    if keywordinfo[0] not in data['packages']:
                        data['packages'][keywordinfo[0]] = set()
                    data['packages'][keywordinfo[0]].add(items[0])
        return data


    def unmask_parser(self):
        self.__validateEntropyCache(self.etpSettingFiles['unmask'],self.etpMtimeFiles['unmask_mtime'])
        return self.__generic_parser(self.etpSettingFiles['unmask'])

    def mask_parser(self):
        self.__validateEntropyCache(self.etpSettingFiles['mask'],self.etpMtimeFiles['mask_mtime'])
        return self.__generic_parser(self.etpSettingFiles['mask'])

    def system_mask_parser(self):
        self.__validateEntropyCache(self.etpSettingFiles['system_mask'],self.etpMtimeFiles['system_mask_mtime'])
        return self.__generic_parser(self.etpSettingFiles['system_mask'])

    def license_mask_parser(self):
        self.__validateEntropyCache(self.etpSettingFiles['license_mask'],self.etpMtimeFiles['license_mask_mtime'])
        return self.__generic_parser(self.etpSettingFiles['license_mask'])

    def repos_license_whitelist_parser(self):
        data = {}
        for repoid in self.etpSettingFiles['repos_license_whitelist']:
            self.__validateEntropyCache(self.etpSettingFiles['repos_license_whitelist'][repoid],self.etpMtimeFiles['repos_license_whitelist'][repoid], repoid = repoid)
            data[repoid] = self.__generic_parser(self.etpSettingFiles['repos_license_whitelist'][repoid])
        return data

    def repos_mask_parser(self):
        data = {}
        for repoid in self.etpSettingFiles['repos_mask']:
            self.__validateEntropyCache(self.etpSettingFiles['repos_mask'][repoid],self.etpMtimeFiles['repos_mask'][repoid], repoid = repoid)
            data[repoid] = self.__generic_parser(self.etpSettingFiles['repos_mask'][repoid])
            # why ? line = line.split()[0] in the previous one?
        return data

    def repos_system_mask_parser(self):
        data = []
        for repoid in self.etpSettingFiles['repos_system_mask']:
            self.__validateEntropyCache(self.etpSettingFiles['repos_system_mask'][repoid],self.etpMtimeFiles['repos_system_mask'][repoid], repoid = repoid)
            data += [x for x in self.__generic_parser(self.etpSettingFiles['repos_system_mask'][repoid]) if x not in data]
            # why ? line = line.split()[0] in the previous one?
        return data

    def system_package_sets_parser(self):
        data = {}
        for set_name in self.etpSettingFiles['system_package_sets']:
            set_filepath = self.etpSettingFiles['system_package_sets'][set_name]
            set_elements = self.entropyTools.extract_packages_from_set_file(set_filepath)
            if set_elements: data[set_name] = set_elements.copy()
        return data

    def system_dirs_parser(self):
        return self.__generic_parser(self.etpSettingFiles['system_dirs'])

    def system_dirs_mask_parser(self):
        return self.__generic_parser(self.etpSettingFiles['system_dirs_mask'])

    def conflicting_tagged_packages_parser(self):
        data = {}
        # keep priority order
        repoids = [x for x in etpRepositoriesOrder if x in self.etpSettingFiles['conflicting_tagged_packages']]
        for repoid in repoids:
            filepath = self.etpSettingFiles['conflicting_tagged_packages'].get(repoid)
            if os.path.isfile(filepath) and os.access(filepath,os.R_OK):
                f = open(filepath,"r")
                content = f.readlines()
                f.close()
                content = [x.strip().rsplit("#",1)[0].strip().split() for x in content if not x.startswith("#") and x.strip()]
                for mydata in content:
                    if len(mydata) < 2: continue
                    data[mydata[0]] = mydata[1:]
        return data

    '''
    internal functions
    '''

    def __generic_parser(self, filepath):
        data = []
        if os.path.isfile(filepath) and os.access(filepath,os.R_OK):
            f = open(filepath,"r")
            content = f.readlines()
            f.close()
            # filter comments and white lines
            content = [x.strip().rsplit("#",1)[0].strip() for x in content if not x.startswith("#") and x.strip()]
            for line in content:
                if line in data: continue
                data.append(line)
        return data

    def __removeRepoCache(self, repoid = None):
        if os.path.isdir(etpConst['dumpstoragedir']):
            if repoid:
                self.Entropy.repository_move_clear_cache(repoid)
                return
            for repoid in etpRepositoriesOrder:
                self.Entropy.repository_move_clear_cache(repoid)
        else:
            os.makedirs(etpConst['dumpstoragedir'])

    def __saveFileMtime(self,toread,tosaveinto):

        if not os.path.isfile(toread):
            currmtime = 0.0
        else:
            currmtime = os.path.getmtime(toread)

        if not os.path.isdir(etpConst['dumpstoragedir']):
            os.makedirs(etpConst['dumpstoragedir'],0775)
            const_setup_perms(etpConst['dumpstoragedir'],etpConst['entropygid'])

        f = open(tosaveinto,"w")
        f.write(str(currmtime))
        f.flush()
        f.close()
        os.chmod(tosaveinto,0664)
        if etpConst['entropygid'] != None:
            os.chown(tosaveinto,0,etpConst['entropygid'])


    def __validateEntropyCache(self, maskfile, mtimefile, repoid = None):

        if os.getuid() != 0: # can't validate if running as user, moreover users can't make changes, so...
            return

        # handle on-disk cache validation
        # in this case, repositories cache
        # if file is changed, we must destroy cache
        if not os.path.isfile(mtimefile):
            # we can't know if it has been updated
            # remove repositories caches
            self.__removeRepoCache(repoid = repoid)
            self.__saveFileMtime(maskfile,mtimefile)
        else:
            # check mtime
            try:
                f = open(mtimefile,"r")
                mtime = f.readline().strip()
                f.close()
                # compare with current mtime
                try:
                    currmtime = str(os.path.getmtime(maskfile))
                except OSError:
                    currmtime = "0.0"
                if mtime != currmtime:
                    self.__removeRepoCache(repoid = repoid)
                    self.__saveFileMtime(maskfile,mtimefile)
            except:
                self.__removeRepoCache(repoid = repoid)
                self.__saveFileMtime(maskfile,mtimefile)
