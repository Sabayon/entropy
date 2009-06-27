# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework core module}.

    This module contains base classes used by entropy.client,
    entropy.server and entropy.services.

    "Singleton" is a class that is inherited from singleton objects.

    SystemSettings is a singleton, pluggable interface which contains
    all the runtime settings (mostly parsed from configuration files
    and inherited from entropy.const -- which contains almost all the
    default values).
    SystemSettings works as a I{dict} object. Due to limitations of
    multiple inherittance when using the Singleton class, SystemSettings
    ONLY mimics a I{dict} AND it's not a subclass of it.

    SystemSettingsPlugin is the base class for building valid SystemSettings
    plugin modules (see entropy.client.interfaces.client or
    entropy.server.interfaces for working examples).

"""
from __future__ import with_statement
import os
from entropy.exceptions import IncorrectParameter, SystemDatabaseError
from entropy.const import etpConst, etpUi, etpSys, const_setup_perms, \
    const_secure_config_file, const_set_nice_level, \
    const_extract_cli_repo_params, etpCache
from entropy.i18n import _
from threading import RLock

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

        @rtype: bool
        @return: instance status, if destroyed or not
        """
        return self.__is_destroyed

    def is_singleton(self):
        """
        Return if the instance is a singleton

        @rtype: bool
        @return: class singleton property, if singleton or not
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

    Sample code:

        >>> # load SystemSettings
        >>> from entropy.core import SystemSettings, SystemSettingsPlugin
        >>> system_settings = SystemSettings()
        >>> class MyPlugin(SystemSettingsPlugin):
        >>>      pass
        >>> my_plugin = MyPlugin('mystuff', None)
        >>> def myparsing_function():
        >>>     return {'abc': 1 }
        >>> my_plugin.add_parser('parser_no_1', myparsing_function)
        >>> system_settings.add_plugin(my_plugin)
        >>> print(system_settings['mystuff']['parser_no_1'])
        {'abc': 1 }
        >>> # let's remove it
        >>> system_settings.remove_plugin('mystuff') # through its plugin_id
        >>> print(system_settings.get('mystuff'))
        None

    """

    def __init__(self, plugin_id, helper_interface):
        """
        SystemSettingsPlugin constructor.

        @param plugin_id: plugin identifier, must be unique
        @type plugin_id: string
        @param helper_interface: any Python object that could
            be of help to your parsers
        @type handler_instance: Python object
        @rtype: None
        @return: None
        """
        self.__parsers = []
        self.__plugin_id = plugin_id
        self._helper = helper_interface
        parser_postfix = "_parser"
        for method in sorted(dir(self)):
            if method == "add_parser":
                continue
            elif method.endswith(parser_postfix) and (method != parser_postfix):
                parser_id = method[:len(parser_postfix)*-1]
                self.__parsers.append((parser_id, getattr(self, method),))

    def get_id(self):
        """
        Returns the unique plugin id passed at construction time.

        @return: plugin identifier
        @rtype: string
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

        @param parser_id: parser identifier, must be unique
        @type parser_id: string
        @param parser_callable: any callable function which has
            the following signature: callable(system_settings_instance)
            can return True to stop further parsers calls
        @type parser_callable: callable
        @return: None
        @rtype: None
        """
        self.__parsers.append((parser_id, parser_callable,))

    def parse(self, system_settings_instance):
        """
        This method is called by SystemSettings instance
        when building its settings metadata.

        Returned data from parser will be put into the SystemSettings
        dict using plugin_id and parser_id keys.
        If returned data is None, SystemSettings dict won't be changed.

        @param system_settings_instance: SystemSettings instance
        @type system_settings_instance: SystemSettings instance
        @return: None
        @rtype: None
        """
        plugin_id = self.get_id()
        for parser_id, parser in self.__parsers:
            data = parser(system_settings_instance)
            if data == None:
                continue
            if not system_settings_instance.has_key(plugin_id):
                system_settings_instance[plugin_id] = {}
            system_settings_instance[plugin_id][parser_id] = data

    def post_setup(self, system_settings_instance):
        """
        This method is called by SystemSettings instance
        after having built all the SystemSettings metadata.
        You can reimplement this and hook your refinement code
        into this method.

        @param system_settings_instance: SystemSettings instance
        @type system_settings_instance: SystemSettings instance
        @return: None
        @rtype: None
        """
        pass

class SystemSettings(Singleton):

    """
    This is the place where all the Entropy settings are stored if
    they are not considered instance constants (etpConst).
    For example, here we store package masking cache information and
    settings, client-side, server-side and services settings.
    Also, this class mimics a dictionary (even if not inheriting it
    due to development choices).

    Sample code:

        >>> from entropy.core import SystemSettings
        >>> system_settings = SystemSettings()
        >>> system_settings.clear()
        >>> system_settings.destroy()

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
        self.__mutex = RLock() # reentrant lock on purpose

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
            # package masking, live
            'live_packagemasking': {
                'unmask_matches': set(),
                'mask_matches': set(),
            },
        }

        self.__setup_const()
        self.__scan()

    def destroy(self):
        """
        Overloaded method from Singleton.
        "Destroys" the instance.

        @return: None
        @rtype: None
        """
        with self.__mutex:
            self.__is_destroyed = True

    def add_plugin(self, system_settings_plugin_instance):
        """
        This method lets you add custom parsers to SystemSettings.
        Mind that you are responsible of handling your plugin instance
        and remove it before it is destroyed. You can remove the plugin
        instance at any time by issuing remove_plugin.
        Every add_plugin or remove_plugin method will also issue clear()
        for you. This could be bad and it might be removed in future.

        @param plugin_id: plugin identifier
        @type plugin_id: string
        @param system_settings_plugin_instance: valid SystemSettingsPlugin
            instance
        @type system_settings_plugin_instance: SystemSettingsPlugin instance
        @return: None
        @rtype: None
        """
        inst = system_settings_plugin_instance
        if not isinstance(inst,SystemSettingsPlugin):
            raise AttributeError("SystemSettings: expected valid " + \
                    "SystemSettingsPlugin instance")
        with self.__mutex:
            self.__plugins[inst.get_id()] = inst
            self.clear()

    def remove_plugin(self, plugin_id):
        """
        This method lets you remove previously added custom parsers from
        SystemSettings through its plugin identifier. If plugin_id is not
        available, KeyError exception will be raised.
        Every add_plugin or remove_plugin method will also issue clear()
        for you. This could be bad and it might be removed in future.

        @param plugin_id: plugin identifier
        @type plugin_id: basestring
        @return: None
        @rtype: None
        """
        with self.__mutex:
            del self.__plugins[plugin_id]
            self.clear()

    def __setup_const(self):

        """
        Internal method. Does constants initialization.

        @return: None
        @rtype: None
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
            # satisfied packages configuration file
            'satisfied': etpConst['confpackagesdir']+"/package.satisfied",
             # masking configuration files
            'license_mask': etpConst['confpackagesdir']+"/license.mask",
            'system_mask': etpConst['confpackagesdir']+"/system.mask",
            'system_dirs': etpConst['confdir']+"/fsdirs.conf",
            'system_dirs_mask': etpConst['confdir']+"/fsdirsmask.conf",
            'system_rev_symlinks': etpConst['confdir']+"/fssymlinks.conf",
            'hw_hash': etpConst['confdir']+"/.hw.hash",
            'socket_service': etpConst['socketconf'],
            'system': etpConst['entropyconf'],
            'repositories': etpConst['repositoriesconf'],
            'system_package_sets': {},
        })
        self.__setting_files_order.extend([
            'keywords', 'unmask', 'mask', 'satisfied', 'license_mask',
            'system_mask', 'system_package_sets', 'system_dirs',
            'system_dirs_mask', 'socket_service', 'system',
            'system_rev_symlinks', 'hw_hash'
        ])
        self.__setting_files_pre_run.extend(['repositories'])

        dmp_dir = etpConst['dumpstoragedir']
        self.__mtime_files.update({
            'keywords_mtime': dmp_dir+"/keywords.mtime",
            'unmask_mtime': dmp_dir+"/unmask.mtime",
            'mask_mtime': dmp_dir+"/mask.mtime",
            'satisfied_mtime': dmp_dir+"/satisfied.mtime",
            'license_mask_mtime': dmp_dir+"/license_mask.mtime",
            'system_mask_mtime': dmp_dir+"/system_mask.mtime",
        })


    def __scan(self):

        """
        Internal method. Scan settings and fill variables.

        @return: None
        @rtype: None
        """

        def enforce_persistent():
            # merge persistent settings back
            self.__data.update(self.__persistent_settings)
            # restore backed-up settings
            self.__data.update(self.__persistent_settings['backed_up'].copy())

        self.__parse()
        enforce_persistent()

        # plugins support
        for plugin_id in sorted(self.__plugins):
            self.__plugins[plugin_id].parse(self)

        enforce_persistent()

        # run post-SystemSettings setup, plugins hook
        for plugin_id in sorted(self.__plugins):
            self.__plugins[plugin_id].post_setup(self)

    def __setitem__(self, mykey, myvalue):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            # backup here too
            if self.__persistent_settings.has_key(mykey):
                self.__persistent_settings[mykey] = myvalue
            self.__data[mykey] = myvalue

    def __getitem__(self, mykey):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data[mykey]

    def __delitem__(self, mykey):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            del self.__data[mykey]

    def __iter__(self):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return iter(self.__data)

    def __contains__(self, item):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return item in self.__data

    def __cmp__(self, other):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return cmp(self.__data, other)

    def __hash__(self):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return hash(self.__data)

    def __len__(self):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return len(self.__data)

    def get(self, mykey, alt_obj = None):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.get(mykey, alt_obj)

    def has_key(self, mykey):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.has_key(mykey)

    def copy(self):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.copy()

    def fromkeys(self, seq, val = None):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.fromkeys(seq, val)

    def items(self):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.items()

    def iteritems(self):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.iteritems()

    def iterkeys(self):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.iterkeys()

    def keys(self):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.keys()

    def pop(self, mykey, default = None):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.pop(mykey, default)

    def popitem(self):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.popitem()

    def setdefault(self, mykey, default = None):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.setdefault(mykey, default)

    def update(self, kwargs):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.update(kwargs)

    def values(self):
        """
        dict method. See Python dict API reference.
        """
        with self.__mutex:
            return self.__data.values()

    def clear(self):
        """
        dict method. See Python dict API reference.
        Settings are also re-initialized here.

        @return None
        """
        with self.__mutex:
            self.__data.clear()
            self.__setup_const()
            self.__scan()

    def set_persistent_setting(self, persistent_dict):
        """
        Make metadata persistent, the input dict will be merged
        with the base one at every reset call (clear()).

        @param persistent_dict: dictionary to merge
        @type persistent_dict: dict

        @return: None
        @rtype: None
        """
        with self.__mutex:
            self.__persistent_settings.update(persistent_dict)

    def unset_persistent_setting(self, persistent_key):
        """
        Remove dict key from persistent dictionary

        @param persistent_key: key to remove
        @type persistent_dict: dict

        @return: None
        @rtype: None
        """
        with self.__mutex:
            del self.__persistent_settings[persistent_key]
            del self.__data[persistent_key]

    def __setup_package_sets_vars(self):

        """
        This function setups the *files* dictionary about package sets
        that will be read and parsed afterwards by the respective
        internal parser.

        @return: None
        @rtype: None
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

        @return: None
        @rtype: None
        """
        # some parsers must be run BEFORE everything:
        for item in self.__setting_files_pre_run:
            myattr = '_%s_parser' % (item,)
            if not hasattr(self, myattr):
                continue
            func = getattr(self, myattr)
            self.__data[item] = func()

        # parse main settings
        self.__setup_package_sets_vars()

        data = {}
        for item in self.__setting_files_order:
            myattr = '_%s_parser' % (item,)
            if not hasattr(self, myattr):
                continue
            func = getattr(self, myattr)
            self.__data[item] = func()

    def get_setting_files_data(self):
        """
        Return a copy of the internal *files* dictionary.
        This dict contains config file paths and their identifiers.

        @return: dict __setting_files
        @rtype: dict
        """
        with self.__mutex:
            return self.__setting_files.copy()

    def _keywords_parser(self):
        """
        Parser returning package keyword masking metadata
        read from package.keywords file.
        This file contains package mask or unmask directives
        based on package keywords.

        @return: parsed metadata
        @rtype: dict
        """
        # merge universal keywords
        data = {
                'universal': set(),
                'packages': {},
                'repositories': {},
        }

        self.validate_entropy_cache(self.__setting_files['keywords'],
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

        # merge universal keywords
        etpConst['keywords'].clear()
        etpConst['keywords'].update(etpSys['keywords'])
        for keyword in data['universal']:
            etpConst['keywords'].add(keyword)

        return data


    def _unmask_parser(self):
        """
        Parser returning package unmasking metadata read from
        package.unmask file.
        This file contains package unmask directives, allowing
        to enable experimental or *secret* packages.

        @return: parsed metadata
        @rtype: dict
        """
        self.validate_entropy_cache(self.__setting_files['unmask'],
            self.__mtime_files['unmask_mtime'])
        return self.__generic_parser(self.__setting_files['unmask'])

    def _mask_parser(self):
        """
        Parser returning package masking metadata read from
        package.mask file.
        This file contains package mask directives, allowing
        to disable experimental or *secret* packages.

        @return: parsed metadata
        @rtype: dict
        """
        self.validate_entropy_cache(self.__setting_files['mask'],
            self.__mtime_files['mask_mtime'])
        return self.__generic_parser(self.__setting_files['mask'])

    def _satisfied_parser(self):
        """
        Parser returning package forced satisfaction metadata
        read from package.satisfied file.
        This file contains packages which updates as dependency are
        filtered out.

        @return: parsed metadata
        @rtype: dict
        """
        self.validate_entropy_cache(self.__setting_files['satisfied'],
            self.__mtime_files['satisfied_mtime'])
        return self.__generic_parser(self.__setting_files['satisfied'])

    def _system_mask_parser(self):
        """
        Parser returning system packages mask metadata read from
        package.system_mask file.
        This file contains packages that should be always kept
        installed, extending the already defined (in repository database)
        set of atoms.

        @return: parsed metadata
        @rtype: dict
        """
        self.validate_entropy_cache(self.__setting_files['system_mask'],
            self.__mtime_files['system_mask_mtime'])
        return self.__generic_parser(self.__setting_files['system_mask'])

    def _license_mask_parser(self):
        """
        Parser returning packages masked by license metadata read from
        license.mask file.
        Packages shipped with licenses listed there will be masked.

        @return: parsed metadata
        @rtype: dict
        """
        self.validate_entropy_cache(self.__setting_files['license_mask'],
            self.__mtime_files['license_mask_mtime'])
        return self.__generic_parser(self.__setting_files['license_mask'])

    def _system_package_sets_parser(self):
        """
        Parser returning system defined package sets read from
        /etc/entropy/packages/sets.

        @return: parsed metadata
        @rtype: dict
        """
        data = {}
        for set_name in self.__setting_files['system_package_sets']:
            set_filepath = self.__setting_files['system_package_sets'][set_name]
            set_elements = self.entropyTools.extract_packages_from_set_file(
                set_filepath)
            if set_elements:
                data[set_name] = set_elements.copy()
        return data

    def _system_dirs_parser(self):
        """
        Parser returning directories considered part of the base system.

        @return: parsed metadata
        @rtype: dict
        """
        return self.__generic_parser(self.__setting_files['system_dirs'])

    def _system_dirs_mask_parser(self):
        """
        Parser returning directories NOT considered part of the base system.
        Settings here overlay system_dirs_parser.

        @return: parsed metadata
        @rtype: dict
        """
        return self.__generic_parser(self.__setting_files['system_dirs_mask'])

    def _hw_hash_parser(self):
        """
        Hardware hash metadata parser and generator. It returns a theorically
        unique SHA256 hash bound to the computer running this Framework.

        @return: string containing SHA256 hexdigest
        @rtype: string
        """
        hw_hash_file = self.__setting_files['hw_hash']
        if os.access(hw_hash_file, os.R_OK | os.F_OK):
            hash_f = open(hw_hash_file, "r")
            hash_data = hash_f.readline().strip()
            hash_f.close()
            return hash_data

        hash_file_dir = os.path.dirname(hw_hash_file)
        hw_hash_exec = etpConst['etp_hw_hash_gen']
        if os.access(hash_file_dir, os.W_OK) and \
            os.access(hw_hash_exec, os.X_OK | os.F_OK | os.R_OK):
            pipe = os.popen('{ ' + hw_hash_exec + '; } 2>&1', 'r')
            hash_data = pipe.read().strip()
            sts = pipe.close()
            if sts != None:
                return None
            hash_f = open(hw_hash_file, "w")
            hash_f.write(hash_data)
            hash_f.flush()
            hash_f.close()
            return hash_data

    def _system_rev_symlinks_parser(self):
        """
        Parser returning important system symlinks mapping. For example:
            {'/usr/lib': ['/usr/lib64']}
        Useful for reverse matching files belonging to packages.

        @return: dict containing the mapping
        @rtype: dict
        """
        setting_file = self.__setting_files['system_rev_symlinks']
        raw_data = self.__generic_parser(setting_file)
        data = {}
        for line in raw_data:
            line = line.split()
            if len(line) < 2:
                continue
            data[line[0]] = frozenset(line[1:])
        return data

    def _socket_service_parser(self):
        """
        Parses socket service configuration file.
        This file contains information about Entropy remote service ports
        and SSL.

        @return: parsed metadata
        @rtype: dict
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

    def _system_parser(self):

        """
        Parses Entropy system configuration file.

        @return: parsed metadata
        @rtype: dict
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

    def _repositories_parser(self):

        """
        Setup Entropy Client repository settings reading them from
        the relative config file specified in etpConst['repositoriesconf']

        @return: parsed metadata
        @rtype: dict
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

        return data

    def _clear_repository_cache(self, repoid = None):
        """
        Internal method, go away!
        """
        self.__cacher.discard()
        self._clear_dump_cache(etpCache['world_available'])
        self._clear_dump_cache(etpCache['world_update'])
        self._clear_dump_cache(etpCache['critical_update'])
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

        @param filepath: valid path
        @type filepath: string
        @return: raw text extracted from file
        @rtype: list
        """
        return self.entropyTools.generic_file_content_parser(filepath)

    def __remove_repo_cache(self, repoid = None):
        """
        Internal method. Remove repository cache, because not valid anymore.

        @keyword repoid: repository identifier or None
        @type repoid: string or None
        @return: None
        @rtype: None
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

        @param toread: file path to read
        @type toread: string
        @param tosaveinto: path where to save retrieved mtime information
        @type tosaveinto: string
        @return: None
        @rtype: None
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


    def validate_entropy_cache(self, settingfile, mtimefile, repoid = None):
        """
        Internal method. Validates Entropy Cache based on a setting file
        and its stored (cache bound) mtime.

        @param settingfile: path of the setting file
        @type settingfile: string
        @param mtimefile: path where to save retrieved mtime information
        @type mtimefile: string
        @keyword repoid: repository identifier or None
        @type repoid: string or None
        @return: None
        @rtype: None
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
            self.__save_file_mtime(settingfile, mtimefile)
        else:
            # check mtime
            try:
                mtime_f = open(mtimefile,"r")
                mtime = mtime_f.readline().strip()
                mtime_f.close()
                # compare with current mtime
                try:
                    currmtime = str(os.path.getmtime(settingfile))
                except OSError:
                    currmtime = "0.0"
                if mtime != currmtime:
                    self.__remove_repo_cache(repoid = repoid)
                    self.__save_file_mtime(settingfile, mtimefile)
            except (OSError, IOError,):
                self.__remove_repo_cache(repoid = repoid)
                self.__save_file_mtime(settingfile, mtimefile)
