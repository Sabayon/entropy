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
# pylint ~ ok

import os
from entropy.exceptions import IncorrectParameter, SystemDatabaseError
from entropy.const import etpConst, const_setup_perms, etpRepositories, \
    etpRepositoriesOrder
from entropy.i18n import _

class Singleton(object):

    """
    If your class wants to become a sexy Singleton,
    subclass this and replace __init__ with init_singleton
    """

    __is_destroyed = False
    __is_singleton = True
    def __new__(cls, *args, **kwds):
        instance = cls.__dict__.get("__it__")
        if instance != None:
            if not instance.is_destroyed():
                return instance
        cls.__it__ = instance = object.__new__(cls)
        instance.init_singleton(*args, **kwds)
        return instance

    def is_destroyed(self):
        """
        In our world, Singleton instances may be destroyed,
        this is done by setting a private bool var __is_destroyed

        @return bool
        """
        return self.__is_destroyed

    def is_singleton(self):
        """
        Return if the instance is a singleton

        @return bool
        """
        return self.__is_singleton

class SystemSettings(Singleton):

    """
        This is the place where all the Entropy settings are stored if
        they are not considered instance constants (etpConst).
        For example, here we store package masking cache information and
        settings.
        Also, this class mimics a dictionary (even if not inheriting it
        due to issues with the Singleton class).
    """

    import entropy.tools as entropyTools
    def init_singleton(self, entropy_client_instance = None):

        """
        Replaces __init__ because SystemSettings is a Singleton.
        see Singleton API reference for more information.

        @param entropy_client_instance entropy.client.interfaces.Client
            instance
        @type entropy_client_instance class instance
        """

        self.__data = {}
        self.__is_destroyed = False
        if entropy_client_instance != None:
            from entropy.client.interfaces import Client
            if not isinstance(entropy_client_instance, Client):
                mytxt = _("A valid Client interface instance is needed")
                raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        self.Entropy = entropy_client_instance

        self.__setting_files = {}
        self.__mtime_files = {}
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

        self.__setup_const()
        self.__scan()

    def destroy(self):
        """
        Overloaded method from Singleton.
        "Destroys" the instance.

        @return None
        """
        self.__is_destroyed = True

    def __setup_const(self):

        """
        Internal method. Does the constants initialization.

        @return None
        """

        self.__setting_files.clear()
        self.__mtime_files.clear()

        self.__setting_files.update({
             # keywording configuration files
            'keywords': etpConst['confpackagesdir']+"/package.keywords",
             # unmasking configuration files
            'unmask': etpConst['confpackagesdir']+"/package.unmask",
             # masking configuration files
            'mask': etpConst['confpackagesdir']+"/package.mask",
             # masking configuration files
            'license_mask': etpConst['confpackagesdir']+"/license.mask",
            'repos_system_mask': {},
            'system_mask': etpConst['confpackagesdir']+"/system.mask",
            'repos_mask': {},
            'repos_license_whitelist': {},
            'system_package_sets': {},
            'conflicting_tagged_packages': {},
            'system_dirs': etpConst['confdir']+"/fsdirs.conf",
            'system_dirs_mask': etpConst['confdir']+"/fsdirsmask.conf",
            'socket_service': etpConst['socketconf'],
        })

        ## XXX trunk support, for a while - exp. date 10/10/2009
        trunk_fsdirs_conf = "../conf/fsdirs.conf"
        trunk_fsdirsmask_conf = "../conf/fsdirsmask.conf"
        if os.path.isfile(trunk_fsdirs_conf):
            self.__setting_files['system_dirs'] = trunk_fsdirs_conf
        if os.path.isfile(trunk_fsdirsmask_conf):
            self.__setting_files['system_dirs_mask'] = trunk_fsdirsmask_conf

        dmp_dir = etpConst['dumpstoragedir']
        self.__mtime_files.update({
            'keywords_mtime': dmp_dir+"/keywords.mtime",
            'unmask_mtime': dmp_dir+"/unmask.mtime",
            'mask_mtime': dmp_dir+"/mask.mtime",
            'license_mask_mtime': dmp_dir+"/license_mask.mtime",
            'system_mask_mtime': dmp_dir+"/system_mask.mtime",
            'repos_system_mask': {},
            'repos_mask': {},
            'repos_license_whitelist': {},
        })


    def __scan(self):

        """
        Internal method. Scan settings and fill variables.

        @return None
        """

        self.__data.update(self.__parse())
        # merge universal keywords
        for keyword in self.__data['keywords']['universal']:
            etpConst['keywords'].add(keyword)

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
        mask_installed = []
        mask_installed_keys = {}
        if self.Entropy != None:
            while (self.Entropy.clientDbconn != None):
                try:
                    self.Entropy.clientDbconn.validateDatabase()
                except SystemDatabaseError:
                    break
                mc_cache = set()
                m_list = self.__data['repos_system_mask'] + \
                    self.__data['system_mask']
                for atom in m_list:
                    m_ids, m_r = self.Entropy.clientDbconn.atomMatch(atom,
                        multiMatch = True)
                    if m_r != 0:
                        continue
                    mykey = self.entropyTools.dep_getkey(atom)
                    if mykey not in mask_installed_keys:
                        mask_installed_keys[mykey] = set()
                    for m_id in m_ids:
                        if m_id in mc_cache:
                            continue
                        mc_cache.add(m_id)
                        mask_installed.append(m_id)
                        mask_installed_keys[mykey].add(m_id)
                break
        self.__data['repos_system_mask_installed'] = mask_installed
        self.__data['repos_system_mask_installed_keys'] = mask_installed_keys

        # Live package masking
        self.__data.update(self.__persistent_settings)

    def __setitem__(self, mykey, myvalue):
        """
        dict method. See Python dict API reference.
        """
        if self.__persistent_settings.has_key(mykey): # backup here too
            self.__persistent_settings[mykey] = myvalue
        self.__data[mykey] = myvalue

    def __getitem__(self, mykey):
        """
        dict method. See Python dict API reference.
        """
        return self.__data[mykey]

    def __delitem__(self, mykey):
        """
        dict method. See Python dict API reference.
        """
        del self.__data[mykey]

    def __iter__(self):
        """
        dict method. See Python dict API reference.
        """
        return iter(self.__data)

    def __contains__(self, item):
        """
        dict method. See Python dict API reference.
        """
        return item in self.__data

    def __cmp__(self, other):
        """
        dict method. See Python dict API reference.
        """
        return cmp(self.__data, other)

    def __hash__(self):
        """
        dict method. See Python dict API reference.
        """
        return hash(self.__data)

    def __len__(self):
        """
        dict method. See Python dict API reference.
        """
        return len(self.__data)

    def get(self, mykey):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.get(mykey)

    def has_key(self, mykey):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.has_key(mykey)

    def copy(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.copy()

    def fromkeys(self, seq, val = None):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.fromkeys(seq, val)

    def items(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.items()

    def iteritems(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.iteritems()

    def iterkeys(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.iterkeys()

    def keys(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.keys()

    def pop(self, mykey, default = None):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.pop(mykey, default)

    def popitem(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.popitem()

    def setdefault(self, mykey, default = None):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.setdefault(mykey, default)

    def update(self, **kwargs):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.update(kwargs)

    def values(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.values()

    def clear(self):
        """
        dict method. See Python dict API reference.
        Settings are also re-initialized here.

        @return None
        """
        self.__data.clear()
        self.__setup_const()
        self.__scan()

    def __setup_setting_vars(self):

        """
        This function setups the *mtimes* and *files* dictionaries
        that will be read and parsed afterwards by respective
        internal parsers.

        @return None
        """

        dmp_dir = etpConst['dumpstoragedir']
        for repoid in etpRepositoriesOrder:

            repos_mask_setting = {}
            repos_mask_mtime = {}
            repos_lic_wl_setting = {}
            repos_lic_wl_mtime = {}
            repo_data = etpRepositories[repoid]
            repos_sm_mask_setting = {}
            repos_sm_mask_mtime = {}
            confl_tagged = {}

            maskpath = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasemaskfile'])
            wlpath = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabaselicwhitelistfile'])
            sm_path = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasesytemmaskfile'])
            ct_path = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabaseconflictingtaggedfile'])

            if os.path.isfile(maskpath) and os.access(maskpath, os.R_OK):
                repos_mask_setting[repoid] = maskpath
                repos_mask_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabasemaskfile'] + ".mtime"

            if os.path.isfile(wlpath) and os.access(wlpath, os.R_OK):
                repos_lic_wl_setting[repoid] = wlpath
                repos_lic_wl_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabaselicwhitelistfile'] + \
                    ".mtime"

            if os.path.isfile(sm_path) and os.access(sm_path, os.R_OK):
                repos_sm_mask_setting[repoid] = sm_path
                repos_sm_mask_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabasesytemmaskfile'] + \
                    ".mtime"
            if os.path.isfile(ct_path) and os.access(ct_path, os.R_OK):
                confl_tagged[repoid] = ct_path

            self.__setting_files['repos_mask'].update(repos_mask_setting)
            self.__mtime_files['repos_mask'].update(repos_mask_mtime)

            self.__setting_files['repos_license_whitelist'].update(
                repos_lic_wl_setting)
            self.__mtime_files['repos_license_whitelist'].update(
                repos_lic_wl_mtime)

            self.__setting_files['repos_system_mask'].update(
                repos_sm_mask_setting)
            self.__mtime_files['repos_system_mask'].update(
                repos_sm_mask_mtime)

            self.__setting_files['conflicting_tagged_packages'].update(
                confl_tagged)

    def __setup_package_sets_vars(self):

        """
        This function setups the *files* dictionary about package sets
        that will be read and parsed afterwards by the respective
        internal parser.

        @return None
        """

        # user defined package sets
        sets_dir = etpConst['confsetsdir']
        pkg_set_data = {}
        if (os.path.isdir(sets_dir) and os.access(sets_dir, os.R_OK)):
            set_files = [x for x in os.listdir(sets_dir) if \
                (os.path.isfile(os.path.join(sets_dir, x)) and \
                os.access(os.path.join(sets_dir, x),os.R_OK))]
            for set_file in set_files:
                try:
                    set_file = str(set_file)
                except (UnicodeDecodeError, UnicodeEncodeError,):
                    continue
                pkg_set_data[set_file] = os.path.join(sets_dir, set_file)
        self.__setting_files['system_package_sets'].update(pkg_set_data)

    def __parse(self):
        """
        This is the main internal parsing method.
        *files* and *mtimes* dictionaries are prepared and
        parsed just a few lines later.

        @return dict settings metadata
        """
        # parse main settings
        self.__setup_setting_vars()
        self.__setup_package_sets_vars()

        data = {}
        for item in self.__setting_files:
            myattr = '%s_parser' % (item,)
            if not hasattr(self, myattr):
                continue
            func = getattr(self, myattr)
            data[item] = func()
        return data

    def get_setting_files_data(self):
        """
        Return a copy of the internal *files* dictionary.
        This dict contains config file paths and their identifiers.

        @return dict __setting_files
        """
        return self.__setting_files.copy()

    def get_mtime_files_data(self):
        """
        Return a copy of the internal *mtime* dictionary.
        This dict contains config file paths and their current mtime.

        @return dict __mtime_files
        """
        return self.__mtime_files.copy()

    def keywords_parser(self):
        """
        Parser returning package keyword masking metadata
        read from package.keywords file.
        This file contains package mask or unmask directives
        based on package keywords.

        @return dict data
        """
        data = {
                'universal': set(),
                'packages': {},
                'repositories': {},
        }

        self.__validate_entropy_cache(self.__setting_files['keywords'],
            self.__mtime_files['keywords_mtime'])
        content = [x.split() for x in \
            self.__generic_parser(self.__setting_files['keywords']) \
            if len(x.split()) < 4]
        for keywordinfo in content:
            # skip wrong lines
            if len(keywordinfo) > 3:
                continue
            # inversal keywording, check if it's not repo=
            if len(keywordinfo) == 1:
                if keywordinfo[0].startswith("repo="):
                    continue
                # convert into entropy format
                if keywordinfo[0] == "**":
                    keywordinfo[0] = ""
                data['universal'].add(keywordinfo[0])
                continue
            # inversal keywording, check if it's not repo=
            if len(keywordinfo) in (2, 3,):
                # repo=?
                if keywordinfo[0].startswith("repo="):
                    continue
                # add to repo?
                items = keywordinfo[1:]
                # convert into entropy format
                if keywordinfo[0] == "**":
                    keywordinfo[0] = ""
                reponame = [x for x in items if x.startswith("repo=") \
                    and (len(x.split("=")) == 2)]
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
                    elif "*" not in \
                        data['repositories'][reponame][keywordinfo[0]]:

                        item = [x for x in items if not x.startswith("repo=")]
                        data['repositories'][reponame][keywordinfo[0]].add(
                            item[0])
                elif len(items) == 2:
                    # it's going to be a faulty line!!??
                    # can't have two items and no repo=
                    continue
                else:
                    # add keyword to packages
                    if keywordinfo[0] not in data['packages']:
                        data['packages'][keywordinfo[0]] = set()
                    data['packages'][keywordinfo[0]].add(items[0])
        return data


    def unmask_parser(self):
        """
        Parser returning package unmasking metadata read from
        package.unmask file.
        This file contains package unmask directives, allowing
        to enable experimental or *secret* packages.

        @return list parsed data
        """
        self.__validate_entropy_cache(self.__setting_files['unmask'],
            self.__mtime_files['unmask_mtime'])
        return self.__generic_parser(self.__setting_files['unmask'])

    def mask_parser(self):
        """
        Parser returning package masking metadata read from
        package.mask file.
        This file contains package mask directives, allowing
        to disable experimental or *secret* packages.

        @return list parsed data
        """
        self.__validate_entropy_cache(self.__setting_files['mask'],
            self.__mtime_files['mask_mtime'])
        return self.__generic_parser(self.__setting_files['mask'])

    def system_mask_parser(self):
        """
        Parser returning system packages mask metadata read from
        package.system_mask file.
        This file contains packages that should be always kept
        installed, extending the already defined (in repository database)
        set of atoms.

        @return list parsed data
        """
        self.__validate_entropy_cache(self.__setting_files['system_mask'],
            self.__mtime_files['system_mask_mtime'])
        return self.__generic_parser(self.__setting_files['system_mask'])

    def license_mask_parser(self):
        """
        Parser returning packages masked by license metadata read from
        license.mask file.
        Packages shipped with licenses listed there will be masked.

        @return list parsed data
        """
        self.__validate_entropy_cache(self.__setting_files['license_mask'],
            self.__mtime_files['license_mask_mtime'])
        return self.__generic_parser(self.__setting_files['license_mask'])

    def repos_license_whitelist_parser(self):
        """
        Parser returning licenses considered accepted by default
        (= GPL compatibles) read from package.lic_whitelist.

        @return dict parsed data
        """
        data = {}
        for repoid in self.__setting_files['repos_license_whitelist']:
            self.__validate_entropy_cache(
                self.__setting_files['repos_license_whitelist'][repoid],
                self.__mtime_files['repos_license_whitelist'][repoid],
                repoid = repoid)
            data[repoid] = self.__generic_parser(
                self.__setting_files['repos_license_whitelist'][repoid])
        return data

    def repos_mask_parser(self):
        """
        Parser returning packages masked at repository level read from
        packages.db.mask inside the repository database directory.

        @return dict parsed data
        """
        data = {}
        for repoid in self.__setting_files['repos_mask']:
            self.__validate_entropy_cache(
                self.__setting_files['repos_mask'][repoid],
                self.__mtime_files['repos_mask'][repoid], repoid = repoid)
            data[repoid] = self.__generic_parser(
                self.__setting_files['repos_mask'][repoid])
            # why ? line = line.split()[0] in the previous one?
        return data

    def repos_system_mask_parser(self):
        """
        Parser returning system packages mask metadata read from
        packages.db.system_mask file inside the repository directory.
        This file contains packages that should be always kept
        installed, extending the already defined (in repository database)
        set of atoms.

        @return dict parsed data
        """
        data = []
        for repoid in self.__setting_files['repos_system_mask']:
            self.__validate_entropy_cache(
                self.__setting_files['repos_system_mask'][repoid],
                self.__mtime_files['repos_system_mask'][repoid],
                repoid = repoid)
            data += [x for x in self.__generic_parser(
                self.__setting_files['repos_system_mask'][repoid]) if x \
                    not in data]
            # why ? line = line.split()[0] in the previous one?
        return data

    def system_package_sets_parser(self):
        """
        Parser returning system defined package sets read from
        /etc/entropy/packages/sets.

        @return dict parsed data
        """
        data = {}
        for set_name in self.__setting_files['system_package_sets']:
            set_filepath = self.__setting_files['system_package_sets'][set_name]
            set_elements = self.entropyTools.extract_packages_from_set_file(
                set_filepath)
            if set_elements:
                data[set_name] = set_elements.copy()
        return data

    def system_dirs_parser(self):
        """
        Parser returning directories considered part of the base system.

        @return list parsed data
        """
        return self.__generic_parser(self.__setting_files['system_dirs'])

    def system_dirs_mask_parser(self):
        """
        Parser returning directories NOT considered part of the base system.
        Settings here overlay system_dirs_parser.

        @return list parsed data
        """
        return self.__generic_parser(self.__setting_files['system_dirs_mask'])

    def conflicting_tagged_packages_parser(self):
        """
        Parser returning packages that could have been installed because
        they aren't in the same scope, but ending up creating critical
        issues. You can see it as a configurable conflict map.

        @return dict parsed data
        """
        data = {}
        # keep priority order
        repoids = [x for x in etpRepositoriesOrder if x in \
            self.__setting_files['conflicting_tagged_packages']]
        for repoid in repoids:
            filepath = self.__setting_files['conflicting_tagged_packages'].get(
                repoid)
            if os.path.isfile(filepath) and os.access(filepath, os.R_OK):
                confl_f = open(filepath,"r")
                content = confl_f.readlines()
                confl_f.close()
                content = [x.strip().rsplit("#", 1)[0].strip().split() for x \
                    in content if not x.startswith("#") and x.strip()]
                for mydata in content:
                    if len(mydata) < 2:
                        continue
                    data[mydata[0]] = mydata[1:]
        return data

    def socket_service_parser(self):
        """
        Parses socket service configuration file.
        This file contains information about Entropy remote service ports
        and SSL.

        @return dict data
        """

        data = etpConst['socket_service'].copy()

        sock_conf = self.__setting_files['socket_service']
        if not (os.path.isfile(sock_conf) and \
            os.access(sock_conf,os.R_OK)):
            return data

        socket_f = open(sock_conf,"r")
        socketconf = [x.strip() for x in socket_f.readlines()  if \
            x.strip() and not x.strip().startswith("#")]
        socket_f.close()

        for line in socketconf:

            if line.startswith("listen|") and (len(line.split("|")) > 1):

                item = line.split("|")[1].strip()
                if item:
                    data['hostname'] = item

            elif line.startswith("listen-port|") and \
                (len(line.split("|")) > 1):

                item = line.split("|")[1].strip()
                try:
                    item = int(item)
                    data['port'] = item
                except ValueError:
                    pass

            elif line.startswith("listen-timeout|") and \
                (len(line.split("|")) > 1):

                item = line.split("|")[1].strip()
                try:
                    item = int(item)
                    data['timeout'] = item
                except ValueError:
                    pass

            elif line.startswith("listen-threads|") and \
                (len(line.split("|")) > 1):

                item = line.split("|")[1].strip()
                try:
                    item = int(item)
                    data['threads'] = item
                except ValueError:
                    pass

            elif line.startswith("session-ttl|") and \
                (len(line.split("|")) > 1):

                item = line.split("|")[1].strip()
                try:
                    item = int(item)
                    data['session_ttl'] = item
                except ValueError:
                    pass

            elif line.startswith("max-connections|") and \
                (len(line.split("|")) > 1):

                item = line.split("|")[1].strip()
                try:
                    item = int(item)
                    data['max_connections'] = item
                except ValueError:
                    pass

            elif line.startswith("ssl-port|") and \
                (len(line.split("|")) > 1):

                item = line.split("|")[1].strip()
                try:
                    item = int(item)
                    data['ssl_port'] = item
                except ValueError:
                    pass

            elif line.startswith("disabled-commands|") and \
                (len(line.split("|")) > 1):

                disabled_cmds = line.split("|")[1].strip().split()
                for disabled_cmd in disabled_cmds:
                    data['disabled_cmds'].add(disabled_cmd)

            elif line.startswith("ip-blacklist|") and \
                (len(line.split("|")) > 1):

                ips_blacklist = line.split("|")[1].strip().split()
                for ip_blacklist in ips_blacklist:
                    data['ip_blacklist'].add(ip_blacklist)

        return data

    def __generic_parser(self, filepath):
        """
        Internal method. This is the generic file parser here.

        @param filepath valid path
        @type filepath basestring
        @return list parsed data
        """
        data = []
        if os.path.isfile(filepath) and os.access(filepath, os.R_OK):
            gen_f = open(filepath,"r")
            content = gen_f.readlines()
            gen_f.close()
            # filter comments and white lines
            content = [x.strip().rsplit("#", 1)[0].strip() for x in content \
                if not x.startswith("#") and x.strip()]
            for line in content:
                if line in data:
                    continue
                data.append(line)
        return data

    def __remove_repo_cache(self, repoid = None):
        """
        Internal method. Remove repository cache, because not valid anymore.

        @param repoid repository identifier or None
        @type repoid basestring or None
        @return None
        """
        if os.path.isdir(etpConst['dumpstoragedir']):
            if repoid and (self.Entropy != None):
                self.Entropy.repository_move_clear_cache(repoid)
                return
            if self.Entropy != None:
                for repoid in etpRepositoriesOrder:
                    self.Entropy.repository_move_clear_cache(repoid)
        else:
            os.makedirs(etpConst['dumpstoragedir'])

    def __save_file_mtime(self, toread, tosaveinto):
        """
        Internal method. Save mtime of a file to another file.

        @param toread file path to read
        @type toread basestring
        @param tosaveinto path where to save retrieved mtime information
        @type tosaveinto basestring
        @return None
        """
        if not os.path.isfile(toread):
            currmtime = 0.0
        else:
            currmtime = os.path.getmtime(toread)

        if not os.path.isdir(etpConst['dumpstoragedir']):
            os.makedirs(etpConst['dumpstoragedir'], 0775)
            const_setup_perms(etpConst['dumpstoragedir'],
                etpConst['entropygid'])

        mtime_f = open(tosaveinto,"w")
        mtime_f.write(str(currmtime))
        mtime_f.flush()
        mtime_f.close()
        os.chmod(tosaveinto, 0664)
        if etpConst['entropygid'] != None:
            os.chown(tosaveinto, 0, etpConst['entropygid'])


    def __validate_entropy_cache(self, maskfile, mtimefile, repoid = None):
        """
        Internal method. Validates Entropy Cache

        @param maskfile path of the setting file
        @type maskfile basestring
        @param mtimefile path where to save retrieved mtime information
        @type mtimefile basestring
        @param repoid repository identifier or None
        @type repoid basestring or None
        @return None
        """

        # can't validate if running as user, moreover
        # users can't make changes, so...
        if os.getuid() != 0:
            return

        # handle on-disk cache validation
        # in this case, repositories cache
        # if file is changed, we must destroy cache
        if not os.path.isfile(mtimefile):
            # we can't know if it has been updated
            # remove repositories caches
            self.__remove_repo_cache(repoid = repoid)
            self.__save_file_mtime(maskfile, mtimefile)
        else:
            # check mtime
            try:
                mtime_f = open(mtimefile,"r")
                mtime = mtime_f.readline().strip()
                mtime_f.close()
                # compare with current mtime
                try:
                    currmtime = str(os.path.getmtime(maskfile))
                except OSError:
                    currmtime = "0.0"
                if mtime != currmtime:
                    self.__remove_repo_cache(repoid = repoid)
                    self.__save_file_mtime(maskfile, mtimefile)
            except (OSError, IOError,):
                self.__remove_repo_cache(repoid = repoid)
                self.__save_file_mtime(maskfile, mtimefile)
