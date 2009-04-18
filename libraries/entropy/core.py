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
from __future__ import with_statement
import os
from entropy.exceptions import IncorrectParameter, SystemDatabaseError
from entropy.const import etpConst, etpUi, etpSys, const_setup_perms, \
    etpRepositories, etpRepositoriesOrder, const_secure_config_file, \
    const_set_nice_level, const_extract_srv_repo_params, etpRepositories, \
    etpRepositoriesExcluded, const_extract_cli_repo_params, etpCache
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

class SystemSettingsPlugin:

    """
    This is a plugin base class for all SystemSettings plugins.
    It allows to add extra parsers (though metadata) to
    SystemSettings.
    Just inherit from this class and call add_parser to add
    your custom parsers.
    SystemSettings will call the parse method, as explained below.
    """

    def __init__(self, plugin_id, helper_interface):
        """
        SystemSettingsPlugin constructor.

        @param plugin_id -- plugin identifier, must be unique
        @type plugin_id basestring
        @param helper_interface -- any Python instance that could
            be of help to your parsers
        @type handler_instance instance
        """
        self.__parsers = []
        self.__plugin_id = plugin_id
        self._helper = helper_interface
        parser_postfix = "_parser"
        for method in dir(self):
            if method == "add_parser":
                continue
            elif method.endswith(parser_postfix) and (method != parser_postfix):
                parser_id = method[:len(parser_postfix)*-1]
                self.__parsers.append((parser_id, getattr(self, method),))

    def get_id(self):
        """
        Returns the unique plugin id passed at construction time.

        @return plugin identifier
        """
        return self.__plugin_id

    def add_parser(self, parser_id, parser_callable):
        """
        You must call this method in order to add your custom
        parsers to the plugin.
        Please note, if your parser method ends with "_parser"
        it will be automatically added this way:

        method: foo_parser
            parser_id => foo
        method: another_fabulous_parser
            parser_id => another_fabulous

        @param parser_id -- parser identifier, must be unique
        @type parser_id basestring
        @param parser_callable -- any callable function which has
            the following signature: callable(system_settings_instance)
            can return True to stop further parsers calls
        @type parser_callable callable
        """
        self.__parsers.append((parser_id, parser_callable,))

    def parse(self, system_settings_instance):
        """
        This method is called by SystemSettings instance
        when building its settings metadata.

        Returned data from parser will be put into the SystemSettings
        dict using plugin_id and parser_id keys.
        If returned data is None, SystemSettings dict won't be changed.

        @param system_settings_instance -- SystemSettings instance
        @type system_settings_instance SystemSettings instance
        """
        plugin_id = self.get_id()
        for parser_id, parser in self.__parsers:
            data = parser(system_settings_instance)
            if data == None:
                continue
            if not system_settings_instance.has_key(plugin_id):
                system_settings_instance[plugin_id] = {}
            system_settings_instance[plugin_id][parser_id] = data

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
    def init_singleton(self):

        """
        Replaces __init__ because SystemSettings is a Singleton.
        see Singleton API reference for more information.

        """

        from entropy.cache import EntropyCacher
        self.__cacher = EntropyCacher()
        self.__data = {}
        self.__is_destroyed = False

        self.__plugins = {}
        self.__setting_files_order = []
        self.__setting_files_pre_run = []
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
            'backed_up': {},
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

    def add_plugin(self, system_settings_plugin_instance):
        """
        This method lets you add custom parsers to SystemSettings.
        Mind that you are responsible of handling your plugin instance
        and remove it before it is destroyed. You can remove the plugin
        instance at any time by issuing remove_plugin.
        Every add_plugin or remove_plugin method will also issue clear()
        for you. This could be bad and it might be removed in future.

        @param plugin_id -- plugin identifier
        @type plugin_id basestring
        @param system_settings_plugin_instance -- valid SystemSettingsPlugin
            instance
        @type system_settings_plugin_instance SystemSettingsPlugin instance
        """
        inst = system_settings_plugin_instance
        if not isinstance(inst,SystemSettingsPlugin):
            raise AttributeError("SystemSettings: expected valid " + \
                    "SystemSettingsPlugin instance")
        self.__plugins[inst.get_id()] = inst
        self.clear()

    def remove_plugin(self, plugin_id):
        """
        This method lets you remove previously added custom parsers from
        SystemSettings through its plugin identifier. If plugin_id is not
        available, KeyError exception will be raised.
        Every add_plugin or remove_plugin method will also issue clear()
        for you. This could be bad and it might be removed in future.

        @param plugin_id -- plugin identifier
        @type plugin_id basestring
        """
        del self.__plugins[plugin_id]
        self.clear()

    def __setup_const(self):

        """
        Internal method. Does the constants initialization.

        @return None
        """

        del self.__setting_files_order[:]
        del self.__setting_files_pre_run[:]
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
            'system': etpConst['entropyconf'],
            'client': etpConst['clientconf'],
            'server': etpConst['serverconf'],
            'repositories': etpConst['repositoriesconf'],
        })
        self.__setting_files_order.extend([
            'keywords', 'unmask', 'mask', 'license_mask',
            'repos_system_mask', 'system_mask', 'repos_mask',
            'repos_license_whitelist', 'system_package_sets',
            'conflicting_tagged_packages', 'system_dirs',
            'system_dirs_mask', 'socket_service', 'system',
            'client', 'server'
        ])
        self.__setting_files_pre_run.extend(['repositories'])

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

        self.__parse()
        # merge universal keywords
        for keyword in self.__data['keywords']['universal']:
            etpConst['keywords'].add(keyword)

        # live package masking / unmasking
        self.__data.update(
            {
                'live_packagemasking': {
                    'unmask_matches': set(),
                    'mask_matches': set(),
                },
            }
        )


        # plugins support
        for plugin_id in sorted(self.__plugins):
            self.__plugins[plugin_id].parse(self)

        # merge persistent settings back
        self.__data.update(self.__persistent_settings)
        # restore backed-up settings
        self.__data.update(self.__persistent_settings['backed_up'].copy())

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

    def set_persistent_setting(self, persistent_dict):
        """
        Make metadata persistent, the input dict will be merged
        with the base one at every reset call (clear()).

        @param persistent_dict -- dictionary to merge
        @type persistent_dict dict

        @return None
        """
        self.__persistent_settings.update(persistent_dict)

    def unset_persistent_setting(self, persistent_key):
        """
        Remove dict key from persistent dictionary

        @param persistent_key -- key to remove
        @type persistent_dict dict

        @return None
        """
        del self.__persistent_settings[persistent_key]
        del self.__data[persistent_key]

    def __setup_setting_vars(self):

        """
        This function setups the *mtimes* and *files* dictionaries
        that will be read and parsed afterwards by respective
        internal parsers.

        @return None
        """

        dmp_dir = etpConst['dumpstoragedir']
        for repoid in self['repositories']['order']:

            repos_mask_setting = {}
            repos_mask_mtime = {}
            repos_lic_wl_setting = {}
            repos_lic_wl_mtime = {}
            repo_data = self['repositories']['available'][repoid]
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
        # some parsers must be run BEFORE everything:
        for item in self.__setting_files_pre_run:
            myattr = '%s_parser' % (item,)
            if not hasattr(self, myattr):
                continue
            func = getattr(self, myattr)
            self.__data[item] = func()

        # parse main settings
        self.__setup_setting_vars()
        self.__setup_package_sets_vars()

        data = {}
        for item in self.__setting_files_order:
            myattr = '%s_parser' % (item,)
            if not hasattr(self, myattr):
                continue
            func = getattr(self, myattr)
            self.__data[item] = func()

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
        repoids = [x for x in self['repositories']['order'] if x in \
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

            split_line = line.split("|")
            split_line_len = len(split_line)

            if line.startswith("listen|") and (split_line_len > 1):

                item = split_line[1].strip()
                if item:
                    data['hostname'] = item

            elif line.startswith("listen-port|") and \
                (split_line_len > 1):

                item = split_line[1].strip()
                try:
                    item = int(item)
                    data['port'] = item
                except ValueError:
                    continue

            elif line.startswith("listen-timeout|") and \
                (split_line_len > 1):

                item = split_line[1].strip()
                try:
                    item = int(item)
                    data['timeout'] = item
                except ValueError:
                    continue

            elif line.startswith("listen-threads|") and \
                (split_line_len > 1):

                item = split_line[1].strip()
                try:
                    item = int(item)
                    data['threads'] = item
                except ValueError:
                    continue

            elif line.startswith("session-ttl|") and \
                (split_line_len > 1):

                item = split_line[1].strip()
                try:
                    item = int(item)
                    data['session_ttl'] = item
                except ValueError:
                    continue

            elif line.startswith("max-connections|") and \
                (split_line_len > 1):

                item = split_line[1].strip()
                try:
                    item = int(item)
                    data['max_connections'] = item
                except ValueError:
                    continue

            elif line.startswith("ssl-port|") and \
                (split_line_len > 1):

                item = split_line[1].strip()
                try:
                    item = int(item)
                    data['ssl_port'] = item
                except ValueError:
                    continue

            elif line.startswith("disabled-commands|") and \
                (split_line_len > 1):

                disabled_cmds = split_line[1].strip().split()
                for disabled_cmd in disabled_cmds:
                    data['disabled_cmds'].add(disabled_cmd)

            elif line.startswith("ip-blacklist|") and \
                (split_line_len > 1):

                ips_blacklist = split_line[1].strip().split()
                for ip_blacklist in ips_blacklist:
                    data['ip_blacklist'].add(ip_blacklist)

        return data

    def system_parser(self):

        """
        Parses Entropy system configuration file.

        @return dict data
        """

        data = {}
        data['proxy'] = etpConst['proxy'].copy()
        data['name'] = etpConst['systemname']
        data['log_level'] = etpConst['entropyloglevel']

        etp_conf = self.__setting_files['system']
        if not os.path.isfile(etp_conf) and \
            os.access(etp_conf,os.R_OK):
            return data

        const_secure_config_file(etp_conf)
        entropy_f = open(etp_conf,"r")
        entropyconf = [x.strip() for x in entropy_f.readlines()  if \
            x.strip() and not x.strip().startswith("#")]
        entropy_f.close()

        for line in entropyconf:

            split_line = line.split("|")
            split_line_len = len(split_line)

            if line.startswith("loglevel|") and \
                (len(line.split("loglevel|")) == 2):

                loglevel = line.split("loglevel|")[1]
                try:
                    loglevel = int(loglevel)
                except ValueError:
                    pass
                if (loglevel > -1) and (loglevel < 3):
                    data['log_level'] = loglevel

            elif line.startswith("ftp-proxy|") and \
                (split_line_len == 2):

                ftpproxy = split_line[1].strip().split()
                if ftpproxy:
                    data['proxy']['ftp'] = ftpproxy[-1]

            elif line.startswith("http-proxy|") and \
                (split_line_len == 2):

                httpproxy = split_line[1].strip().split()
                if httpproxy:
                    data['proxy']['http'] = httpproxy[-1]

            elif line.startswith("proxy-username|") and \
                (split_line_len == 2):

                httpproxy = split_line[1].strip().split()
                if httpproxy:
                    data['proxy']['username'] = httpproxy[-1]

            elif line.startswith("proxy-password|") and \
                (split_line_len == 2):

                httpproxy = split_line[1].strip().split()
                if httpproxy:
                    data['proxy']['password'] = httpproxy[-1]

            elif line.startswith("system-name|") and \
                (split_line_len == 2):

                data['name'] = split_line[1].strip()

            elif line.startswith("nice-level|") and \
                (split_line_len == 2):

                mylevel = split_line[1].strip()
                try:
                    mylevel = int(mylevel)
                    if (mylevel >= -19) and (mylevel <= 19):
                        const_set_nice_level(mylevel)
                except (ValueError,):
                    continue

        return data

    def client_parser(self):

        """
        Parses Entropy client system configuration file.

        @return dict data
        """

        data = {
            'filesbackup': etpConst['filesbackup'],
            'ignore_spm_downgrades': etpConst['spm']['ignore-spm-downgrades'],
            'collisionprotect': etpConst['collisionprotect'],
            'configprotect': etpConst['configprotect'][:],
            'configprotectmask': etpConst['configprotectmask'][:],
            'configprotectskip': etpConst['configprotectskip'][:],
        }

        cli_conf = etpConst['clientconf']
        if not (os.path.isfile(cli_conf) and os.access(cli_conf, os.R_OK)):
            return data

        client_f = open(cli_conf,"r")
        clientconf = [x.strip() for x in client_f.readlines() if \
            x.strip() and not x.strip().startswith("#")]
        client_f.close()
        for line in clientconf:

            split_line = line.split("|")
            split_line_len = len(split_line)

            if line.startswith("filesbackup|") and (split_line_len == 2):

                compatopt = split_line[1].strip().lower()
                if compatopt in ("disable", "disabled","false", "0", "no",):
                    data['filesbackup'] = False

            elif line.startswith("ignore-spm-downgrades|") and \
                (split_line_len == 2):

                compatopt = split_line[1].strip().lower()
                if compatopt in ("enable", "enabled", "true", "1", "yes"):
                    data['ignore_spm_downgrades'] = True

            elif line.startswith("collisionprotect|") and (split_line_len == 2):

                collopt = split_line[1].strip()
                if collopt.lower() in ("0", "1", "2",):
                    data['collisionprotect'] = int(collopt)

            elif line.startswith("configprotect|") and (split_line_len == 2):

                configprotect = split_line[1].strip()
                for myprot in configprotect.split():
                    data['configprotect'].append(
                        unicode(myprot,'raw_unicode_escape'))

            elif line.startswith("configprotectmask|") and \
                (split_line_len == 2):

                configprotect = split_line[1].strip()
                for myprot in configprotect.split():
                    data['configprotectmask'].append(
                        unicode(myprot,'raw_unicode_escape'))

            elif line.startswith("configprotectskip|") and \
                (split_line_len == 2):

                configprotect = split_line[1].strip()
                for myprot in configprotect.split():
                    data['configprotectskip'].append(
                        etpConst['systemroot']+unicode(myprot,
                            'raw_unicode_escape'))

        return data

    def server_parser(self):

        """
        Parses Entropy server system configuration file.

        @return dict data
        """

        data = {
            'repositories': etpConst['server_repositories'].copy(),
            'branches': etpConst['branches'][:],
            'default_repository_id': etpConst['officialserverrepositoryid'],
            'packages_expiration_days': etpConst['packagesexpirationdays'],
            'database_file_format': etpConst['etpdatabasefileformat'],
            'rss': {
                'enabled': etpConst['rss-feed'],
                'name': etpConst['rss-name'],
                'base_url': etpConst['rss-base-url'],
                'website_url': etpConst['rss-website-url'],
                'editor': etpConst['rss-managing-editor'],
                'max_entries': etpConst['rss-max-entries'],
                'light_max_entries': etpConst['rss-light-max-entries'],
            },
        }

        if not os.access(etpConst['serverconf'], os.R_OK):
            return data

        with open(etpConst['serverconf'],"r") as server_f:
            serverconf = [x.strip() for x in server_f.readlines() if x.strip()]

        for line in serverconf:

            split_line = line.split("|")
            split_line_len = len(split_line)

            if line.startswith("branches|") and (split_line_len == 2):

                branches = split_line[1]
                data['branches'] = []
                for branch in branches.split():
                    data['branches'].append(branch)
                if self['repositories']['branch'] not in data['branches']:
                    data['branches'].append(self['repositories']['branch'])
                data['branches'] = sorted(data['branches'])

            elif (line.find("officialserverrepositoryid|") != -1) and \
                (not line.startswith("#")) and (split_line_len == 2):

                data['default_repository_id'] = split_line[1].strip()

            elif (line.find("expiration-days|") != -1) and \
                (not line.startswith("#")) and (split_line_len == 2):

                mydays = split_line[1].strip()
                try:
                    mydays = int(mydays)
                    data['packages_expiration_days'] = mydays
                except ValueError:
                    continue

            elif line.startswith("repository|") and (split_line_len in [5, 6]):

                repoid, repodata = const_extract_srv_repo_params(line,
                    product = self['repositories']['product'])
                if repoid in data['repositories']:
                    # just update mirrors
                    data['repositories'][repoid]['mirrors'].extend(
                        repodata['mirrors'])
                else:
                    data['repositories'][repoid] = repodata.copy()

            elif line.startswith("database-format|") and (split_line_len == 2):

                fmt = split_line[1]
                if fmt in etpConst['etpdatabasesupportedcformats']:
                    data['database_file_format'] = fmt

            elif line.startswith("rss-feed|") and (split_line_len == 2):

                feed = split_line[1]
                if feed in ("enable", "enabled", "true", "1"):
                    data['rss']['enabled'] = True
                elif feed in ("disable", "disabled", "false", "0", "no",):
                    data['rss']['enabled'] = False

            elif line.startswith("rss-name|") and (split_line_len == 2):

                feedname = line.split("rss-name|")[1].strip()
                data['rss']['name'] = feedname

            elif line.startswith("rss-base-url|") and (split_line_len == 2):

                data['rss']['base_url'] = line.split("rss-base-url|")[1].strip()
                if not data['rss']['base_url'][-1] == "/":
                    data['rss']['base_url'] += "/"

            elif line.startswith("rss-website-url|") and (split_line_len == 2):

                data['rss']['website_url'] = split_line[1].strip()

            elif line.startswith("managing-editor|") and (split_line_len == 2):

                data['rss']['editor'] = split_line[1].strip()

            elif line.startswith("max-rss-entries|") and (split_line_len == 2):

                try:
                    entries = int(split_line[1].strip())
                    data['rss']['max_entries'] = entries
                except (ValueError, IndexError,):
                    continue

            elif line.startswith("max-rss-light-entries|") and \
                (split_line_len == 2):

                try:
                    entries = int(split_line[1].strip())
                    data['rss']['light_max_entries'] = entries
                except (ValueError, IndexError,):
                    continue

        # expand paths
        for repoid in data['repositories']:
            data['repositories'][repoid]['packages_dir'] = \
                os.path.join(   etpConst['entropyworkdir'],
                                "server",
                                repoid,
                                "packages",
                                etpSys['arch']
                            )
            data['repositories'][repoid]['store_dir'] = \
                os.path.join(   etpConst['entropyworkdir'],
                                "server",
                                repoid,
                                "store",
                                etpSys['arch']
                            )
            data['repositories'][repoid]['upload_dir'] = \
                os.path.join(   etpConst['entropyworkdir'],
                                "server",
                                repoid,
                                "upload",
                                etpSys['arch']
                            )
            data['repositories'][repoid]['database_dir'] = \
                os.path.join(   etpConst['entropyworkdir'],
                                "server",
                                repoid,
                                "database",
                                etpSys['arch']
                            )
            data['repositories'][repoid]['packages_relative_path'] = \
                os.path.join(   self['repositories']['product'],
                                repoid,
                                "packages",
                                etpSys['arch']
                            )+"/"
            data['repositories'][repoid]['database_relative_path'] = \
                os.path.join(   self['repositories']['product'],
                                repoid,
                                "database",
                                etpSys['arch']
                            )+"/"

        # Support for shell variables
        shell_repoid = os.getenv('ETP_REPO')
        if shell_repoid:
            data['default_repository_id'] = shell_repoid

        expiration_days = os.getenv('ETP_EXPIRATION_DAYS')
        if expiration_days:
            try:
                expiration_days = int(expiration_days)
                data['packages_expiration_days'] = expiration_days
            except ValueError:
                pass

        return data

    def repositories_parser(self):

        """
        Setup Entropy Client repository settings reading them from
        the relative config file specified in etpConst['repositoriesconf']

        @return None
        """

        data = {
            'available': {},
            'excluded': {},
            'order': [],
            'product': etpConst['product'],
            'branch': etpConst['branch'],
            'default_repository': etpConst['officialrepositoryid'],
            'transfer_limit': etpConst['downloadspeedlimit'],
            'security_advisories_url': etpConst['securityurl'],
        }

        # kept for backward compatibility
        # XXX will be removed before 10-10-2009
        etpRepositories.clear()
        etpRepositoriesExcluded.clear()
        del etpRepositoriesOrder[:]

        repo_conf = etpConst['repositoriesconf']
        if not (os.path.isfile(repo_conf) and os.access(repo_conf, os.R_OK)):
            return data

        repo_f = open(repo_conf,"r")
        repositoriesconf = [x.strip() for x in repo_f.readlines() if x.strip()]
        repo_f.close()

        # setup product and branch first
        for line in repositoriesconf:

            split_line = line.split("|")
            split_line_len = len(split_line)

            if (line.find("product|") != -1) and \
                (not line.startswith("#")) and (split_line_len == 2):

                data['product'] = split_line[1]

            elif (line.find("branch|") != -1) and \
                (not line.startswith("#")) and (split_line_len == 2):

                branch = split_line[1].strip()
                data['branch'] = branch
                if not os.path.isdir(etpConst['packagesbindir']+"/"+branch) \
                    and (etpConst['uid'] == 0):

                    try:
                        os.makedirs(etpConst['packagesbindir']+"/"+branch)
                    except (OSError, IOError,):
                        continue

        for line in repositoriesconf:

            split_line = line.split("|")
            split_line_len = len(split_line)

            # populate data['available']
            if (line.find("repository|") != -1) and (split_line_len == 5):

                excluded = False
                my_repodata = data['available']
                if line.startswith("##"):
                    continue
                elif line.startswith("#"):
                    excluded = True
                    my_repodata = data['excluded']
                    line = line[1:]

                reponame, repodata = const_extract_cli_repo_params(line,
                    data['branch'], data['product'])
                if my_repodata.has_key(reponame):

                    my_repodata[reponame]['plain_packages'].extend(
                        repodata['plain_packages'])
                    my_repodata[reponame]['packages'].extend(
                        repodata['packages'])

                    if (not my_repodata[reponame]['plain_database']) and \
                        repodata['plain_database']:

                        my_repodata[reponame]['plain_database'] = \
                            repodata['plain_database']
                        my_repodata[reponame]['database'] = \
                            repodata['database']
                        my_repodata[reponame]['dbrevision'] = \
                            repodata['dbrevision']
                        my_repodata[reponame]['dbcformat'] = \
                            repodata['dbcformat']
                else:

                    my_repodata[reponame] = repodata.copy()
                    if not excluded:
                        data['order'].append(reponame)

            elif (line.find("officialrepositoryid|") != -1) and \
                (not line.startswith("#")) and (split_line_len == 2):

                officialreponame = split_line[1]
                data['default_repository'] = officialreponame

            elif (line.find("downloadspeedlimit|") != -1) and \
                (not line.startswith("#")) and (split_line_len == 2):

                try:
                    myval = int(split_line[1])
                    if myval > 0:
                        data['transfer_limit'] = myval
                    else:
                        data['transfer_limit'] = None
                except (ValueError, IndexError,):
                    data['transfer_limit'] = None

            elif (line.find("securityurl|") != -1) and \
                (not line.startswith("#")) and (split_line_len == 2):

                try:
                    data['security_advisories_url'] = split_line[1]
                except (IndexError, ValueError, TypeError,):
                    continue

        # kept for backward compatibility
        # XXX will be removed before 10-10-2009
        etpRepositories.update(data['available'])
        etpRepositoriesExcluded.update(data['excluded'])
        etpRepositoriesOrder.extend(data['order'])

        return data

    def _clear_repository_cache(self, repoid = None):
        """
        Internal method, go away!
        """
        self.__cacher.sync(wait = True)
        self._clear_dump_cache(etpCache['world_available'])
        self._clear_dump_cache(etpCache['world_update'])
        self._clear_dump_cache(etpCache['check_package_update'])
        self._clear_dump_cache(etpCache['filter_satisfied_deps'])
        self._clear_dump_cache(etpCache['atomMatch'])
        self._clear_dump_cache(etpCache['dep_tree'])
        if repoid != None:
            self._clear_dump_cache("%s/%s%s/" % (
                etpCache['dbMatch'],etpConst['dbnamerepoprefix'],repoid,))
            self._clear_dump_cache("%s/%s%s/" % (
                etpCache['dbSearch'],etpConst['dbnamerepoprefix'],repoid,))

    def _clear_dump_cache(self, dump_name, skip = []):
        """
        Internal method, go away!
        """
        dump_path = os.path.join(etpConst['dumpstoragedir'],dump_name)
        dump_dir = os.path.dirname(dump_path)
        #dump_file = os.path.basename(dump_path)
        for currentdir, subdirs, files in os.walk(dump_dir):
            path = os.path.join(dump_dir,currentdir)
            if skip:
                found = False
                for myskip in skip:
                    if path.find(myskip) != -1:
                        found = True
                        break
                if found: continue
            for item in files:
                if item.endswith(etpConst['cachedumpext']):
                    item = os.path.join(path,item)
                    try:
                        os.remove(item)
                    except (OSError, IOError,):
                        pass
            try:
                if not os.listdir(path):
                    os.rmdir(path)
            except (OSError, IOError,):
                pass

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
            if repoid:
                self._clear_repository_cache(repoid = repoid)
                return
            for repoid in self['repositories']['order']:
                self._clear_repository_cache(repoid = repoid)
        else:
            try:
                os.makedirs(etpConst['dumpstoragedir'])
            except IOError, e:
                if e.errno == 30: # readonly filesystem
                    etpUi['pretend'] = True
                return
            except OSError:
                return

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
            try:
                os.makedirs(etpConst['dumpstoragedir'], 0775)
                const_setup_perms(etpConst['dumpstoragedir'],
                    etpConst['entropygid'])
            except IOError, e:
                if e.errno == 30: # readonly filesystem
                    etpUi['pretend'] = True
                return
            except (OSError,), e:
                # unable to create the storage directory
                # useless to continue
                return

        try:
            mtime_f = open(tosaveinto,"w")
        except IOError, e: # unable to write?
            if e.errno == 30: # readonly filesystem
                etpUi['pretend'] = True
            return
        else:
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
