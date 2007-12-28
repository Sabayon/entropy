#!/usr/bin/python -tt
# -*- coding: iso-8859-1 -*-
#    Yum Exteder (yumex) - A GUI for yum
#    Copyright (C) 2006 Tim Lauridsen < tim<AT>yum-extender<DOT>org > 
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import logging
import gtk
import gobject
import time
import sys,os,traceback

from yum.config import *

# Use iniparse if it exist, else use Python ConfigParser
try:
    from iniparse.compat import ConfigParser,SafeConfigParser
except:
    from ConfigParser import ConfigParser,SafeConfigParser
    
from optparse import OptionParser
from i18n import _
import yum.Errors as Errors
from yum.repos import RepoStorage
import packages


class const:
    ''' This Class contains all the Constants in Yumex'''
    __yumex_version__   = "2.0.2"
    # Paths
    MAIN_PATH = os.path.abspath( os.path.dirname( sys.argv[0] ) );
    GLADE_FILE = MAIN_PATH+'/yumex.glade'  
    if MAIN_PATH == '/usr/share/yumex':    
        PIXMAPS_PATH = '/usr/share/pixmaps/yumex'
    else:
        PIXMAPS_PATH = MAIN_PATH+'/../gfx'
    
    # package categories
    PACKAGE_CATEGORIES = [
        "None",
        "Groups",
        "RPM Groups",
        "Age"]   
        
    YUM_PID_FILE = '/var/run/yum.pid'
    DAY_IN_SECONDS = 86400
    # Page -> Notebook page numbers
    PAGE_REPOS = 0
    PAGE_PKG = 1
    PAGE_OUTPUT = 2
    PAGE_GROUP = 3
    PAGE_QUEUE = 4
    PAGES = {
       'packages'  : PAGE_PKG,
       'repos'     : PAGE_REPOS,
       'output'    : PAGE_OUTPUT,
       'queue'     : PAGE_QUEUE,
       'group'     : PAGE_GROUP
    }

    PACKAGE_PROGRESS_STEPS = ( 0.1, # Depsolve
                               0.5, # Download
                               0.1, # Transaction Test
                               0.3 ) # Running Transaction
    
    SETUP_PROGRESS_STEPS = ( 0.1, # Yum Config
                             0.2, # Repo Setup
                             0.1, # Sacksetup  
                             0.2, # Updates 
                             0.1, # Group 
                             0.3) # get package Lists   
    PACKAGE_CATEGORY_NO = 5
    
# Package Category Control Dict.    
    PACKAGE_CATEGORY_DICT = { 
#
#  [1]           [2]               [3]             [4]     [5]     [6]
#-------------------------------------------------------------------------    
    1 : ( _( 'RPM Groups' ),   'getByAttr',     'group',  True,  True), 
    2 : ( _( 'Repositories' ), 'getByProperty', 'repoid', True,  False ), 
    3 : ( _( 'Architecture' ), 'getByProperty', 'arch',   True,  False ), 
    4 : ( _( 'Sizes' ),        'getBySizes',     '',      False, False ), 
    5 : ( _( 'Age' ),          'getByAge',       '',      False, False )}
    
# [1] : Order in Category Combo
# [2] : Text in Combo
# [3] : Method to get the package by category
# [4] : Parameter to [3].
# [5] : Sort flag
# [6] : Split Categoties and make a tree, insted of a list

    GROUP_PACKAGE_TYPE = {
        'm' : _('Mandatory'),
        'd' : _('Default'),
        'o' : _('Optional'),
        'c' : _('Conditional')
    }


    CREDITS = (
           (('Yum Extender - %s' % __yumex_version__),
           ('Copyright 2005-2007','Tim Lauridsen')),        

           (_("Programming:"),
           ("Tim Lauridsen", "David Zamirski")),

           (_("Translation:"),
           ("Tim Lauridsen (Danish)",
            "MATSUURA Takanori (Japanese)",
            "Rodrigo Padula de Oliveira (Brazilian)",
            "Eric Tanguy (French)",
            "Soohyung Cho (Korean)",
            "Danilo (Italian)",
            "Serta . YILDIZ (Turkish)",
            "Dawid Zamirski, Patryk Zawadzki (Polish)",
            "Piotr Drag (Polish)",
            "Tero Hietanen (Finnish)",
            "Dieter Komendera (German)",
            "Maxim Dziumanenko (Ukrainian)",
            "Novotny Lukas (Czech)",
            "Szll Tams (Hungarian)",
            "Leonid Kanter, Nikita (Russian)",   
            "Diego Alonso (Spanish)",   
            "A Singh Alam (Punjabi)",    
            "Hao Song (Chinese(Simplified))")),


           (_("Special Thanks To:"),
           ("Seth Vidal and the other",
            "Yum developers","without yum there would","not be any Yum Extender",
            "All Yum Extender users"))
          )
    
class YumexRepoList:

    PRIMARY_REPOS = ['extras','updates','core']

    def __init__(self,yumbase):
        self.yumbase = yumbase
        self.repostore = self.yumbase.repos
        self.repos = self.yumbase.repos.repos
        self.enabledInFiles = [r.id for r in self.repostore.listEnabled()]
        self.filters = [] # exclude word list
        
    def clear(self):
        self.yumbase.cleanup()
        self.repostore = self.yumbase.repos
        self.repos = self.yumbase.repos.repos
        
    def setFilter(self,lst):
        self.filters = lst
        
    def getReposToView(self,enablelist):
        ''' 
        Get a list of tuples (enable state,repoid)
        to use in the YumexRepoView.
        
        The list is ordered with the primary repos first and filtered
        with the exclude words  
        '''
        data = []
        ids = self._sortedList()
        for id in ids:
            repo = self.getRepo(id)
            name = repo.name
            gpgcheck = repo.gpgcheck
            if id in enablelist:
                data.append((True,id,name,gpgcheck))
            else:
                data.append((False,id,name,gpgcheck))
        return data

    def getRepo(self,id):
        ''' Get the repo object with the given id'''
        return self.repostore.getRepo(id)
    
    def getEnabledList(self):
        ''' return list of enabled repo ids '''
        return self.enabledInFiles
        
    def _sortedList(self):
        ''' 
        Get an sorted list of repo ids, with the primary ones first
        The list is filtered so the id matching the exclude filters 
        are removed
        '''
        ids = self._getList()
        ids.sort()
        for pri in YumexRepoList.PRIMARY_REPOS:
            if pri in ids:
                ids.remove(pri)
                ids.insert(0,pri)
        return ids
        
    def _getList(self):
        ''' Get an filtered list of repo ids'''
        oklist = []
        ids = self.repos.keys()
        for id in ids:
            if self._filterRepo(id):
                oklist.append(id)
        return oklist
        
    def _filterRepo(self,id):
        ''' Check if an repo id contains any exclude words'''
        for flt in self.filters:
            if flt in id:
                return False
        return True
        
    def enableOnly(self,repos):
        ids = self.repos.keys()
        for id in ids:
            repo = self.getRepo(id)
            if id in repos:
                #print "Enable %s" % id
                repo.enable()
            else:
                repo.disable()
                
class YumexProfile:
    """ Class for handling repo selection Profile """
    def __init__( self ):
        self.profiles = ConfigParser()
        self.filename = '/etc/yumex.profiles.conf'
        self.profiles.read( self.filename )
        self.active=self.profiles.get( "main", "LastProfile" )    
        self.proDict = {}    
        self.load()        

    
    def save( self ):
        if self.profiles.has_section('yum-enabled'):
            self.profiles.remove_section('yum-enabled')
        f=open( self.filename, "w" )
        self.profiles.write( f )
        f.close()
        
    def load( self ):
        self.profiles.read( self.filename )
        self.active=self.profiles.get( "main", "LastProfile" )        
        for p in self.profiles.sections():
            if p != 'main':
                opts = self.profiles.options( p )
                self.proDict[p] = opts

    def getProfile( self, name = None ):
        if not name:
            name = self.active
        if name in self.proDict.keys():
            return self.proDict[name]
        else:
            return None

    def writeProfile( self, repos ):
        self.profiles.remove_section( self.active)    
        return self.addProfile(self.active, repos )                
        

    def getList( self ):
        return self.proDict.keys()

    def getActive( self ):
        return self.active

    def setActive( self, name ):
        if self.profiles.has_section( name ) or name == "yum-enabled":
            self.active = name
            self.profiles.set( "main", "LastProfile", name )        
            self.save()

    def addProfile( self, name, repos ):
        if not self.profiles.has_section( name ):
            self.profiles.add_section( name )
            for r in repos:
                self.profiles.set( name, r, "1" )
            self.save()
            self.load()
            return True
        else:
            return False

                
class YumexQueue:
    def __init__(self):
        self.logger = logging.getLogger('yumex.YumexQueue')
        self.packages = {}
        self.packages['i'] = []
        self.packages['u'] = []
        self.packages['r'] = []
        self.groups = {}
        self.groups['i'] = []
        self.groups['r'] = []

    def clear( self ):
        del self.packages
        self.packages = {}
        self.packages['i'] = []
        self.packages['u'] = []
        self.packages['r'] = []
        self.groups = {}
        self.groups['i'] = []
        self.groups['r'] = []
        
    def get( self, action = None ):        
        if action == None:
            return self.packages
        else:
            return self.packages[action]
            
    def total(self):
        return len(self.packages['i'])+len(self.packages['u'])+len(self.packages['r'])
        
    def add( self, pkg):
        list = self.packages[pkg.action]
        if not pkg in list:
            list.append( pkg )
        self.packages[pkg.action] = list

    def remove( self, pkg):
        list = self.packages[pkg.action]
        if pkg in list:
            list.remove( pkg )
        self.packages[pkg.action] = list

    def addGroup( self, grp, action):
        list = self.groups[action]
        if not grp in list:
            list.append( grp )
        self.groups[action] = list

    def removeGroup( self, grp, action):
        list = self.groups[action]
        if grp in list:
            list.remove( grp )
        self.groups[action] = list

    def hasGroup(self,grp):
        for action in ['i','r']:
            if grp in self.groups[action]:
                return action
        return None
        
    def dump(self):
        self.logger.info(_("Package Queue:"))
        for action in ['install','update','remove']:
            a = action[0]
            list = self.packages[a]
            if len(list) > 0:
                self.logger.info(_(" Packages to %s" % action))
                for pkg in list:
                    self.logger.info(" ---> %s " % str(pkg))
        for action in ['install','remove']:
            a = action[0]
            list = self.groups[a]
            if len(list) > 0:
                self.logger.info(_(" Groups to %s" % action))
                for grp in list:
                    self.logger.info(" ---> %s " % grp)
            
    def getParser(self):
        cp = YumexQueueFile()
        for action in ['install','update','remove']:
            a = action[0]
            list = self.packages[a]
            if len(list) > 0:
                for pkg in list:
                    cp.setPO(action,pkg)      
        return cp

class YumexSaveFile:
    __version__ = '100'

    def __init__(self,typ):
        self.parser = SafeConfigParser()
        self.saveType = typ
        self.parser.add_section('main')
        self.parser.set("main","application","yumex")
        self.parser.set("main","type",self.saveType)
        self.parser.set("main","version",YumexSaveFile.__version__)
    
    def setPO(self,section,pkg):
        (n, a, e, v, r) = pkg.pkgtup
        item = "%s.%s" % (n,a)
        if pkg.epoch:
            e = pkg.epoch
        else:
            e = 0
        repo = pkg.repoid
        value = "%s,%s,%s,%s,%s,%s" % (n,a,e,v,r,repo)
        self.set(section,item ,value)       

    def getPO(self,section,opt):
        value = self.get(section,opt)
        n,a,e,v,r,repo = value.split(',')
        tup = (n,a,e,v,r)
        return tup,repo      
    
    def set(self,section,option,value):
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        self.parser.set(section, option, value)
        
    def get(self,section,option):
        try:
            return self.parser.get(section,option)
        except NoSectionError,NoOptionError:
            return None

    def save(self,fp):
        self.parser.write(fp)

    def load(self,fp):
        self.parser = SafeConfigParser()
        self.parser.readfp(fp)
        try:
            appl = self.parser.get('main','application')
            ver = self.parser.get('main','version')
            typ = self.parser.get('main','type')
            if appl != 'yumex':
                return -1, _("Wrong file application (%s)" % appl)
            if typ != self.saveType:
                return -1, _("Wrong file type (%s)" % type)
            if ver != YumexSaveFile.__version__:
                return -1, _("Wrong file version (%s)" % ver)
            return 0, "file ok"
        except NoSectionError,NoOptionError:
            return -1,"Error in fileformat"
        
class YumexQueueFile(YumexSaveFile):
    def __init__(self):
        YumexSaveFile.__init__(self,'queue')
        
    def getList(self,action):
        dict = {}
        try:
            options = self.parser.options(action)
            for opt in options:
                tup,repo = self.getPO(action,opt) 
                if dict.has_key(repo):
                    lst = dict[repo]
                    lst.append(tup)
                    dict[repo] = lst
                else:
                    dict[repo] = [tup]
            return dict
        except NoSectionError:
            return {}
               
class YumexConf( BaseConfig ):
    """ Yum Extender Config Setting"""
    autorefresh = BoolOption( True )
    recentdays = IntOption( 14 )
    debug = BoolOption( False )
    plugins = BoolOption( True)
    usecache = BoolOption( False )
    proxy = Option()
    exclude = ListOption()
    repo_exclude = ListOption(['debug','source'])
    fullobsoletion = BoolOption( False )
    yumdebuglevel = IntOption( 2 )
    font_console = Option( 'Monospace 8' )
    font_pkgdesc = Option( 'Monospace 8' )
    color_console = Option( '#68228B' )
    color_pkgdesc = Option( '#68228B' )   
    color_install = Option( 'darkgreen' )
    color_update = Option( 'red' )
    color_normal = Option( 'black' )
    color_obsolete = Option( 'blue' )
    filelist = BoolOption( False )
    changelog = BoolOption( False )
    disable_repo_page = BoolOption( False )
    branding_title = Option('Yum Extender')
    
    #
    # This routines are taken from config.py yum > 3.2.2
    # They are because we want the config save to work
    # better with older Yum version (EL5 & FC6)
    #
    
    def write(self, fileobj, section=None, always=()):
        '''Write out the configuration to a file-like object

        @param fileobj: File-like object to write to
        @param section: Section name to use. If not-specified the section name
            used during parsing will be used.
        @param always: A sequence of option names to always write out.
            Options not listed here will only be written out if they are at
            non-default values. Set to None to dump out all options.
        '''
        # Write section heading
        if section is None:
            if self._section is None:
                raise ValueError("not populated, don't know section")
            section = self._section

        # Updated the ConfigParser with the changed values    
        cfgOptions = self.cfg.options(section)
        for name,value in self.iteritems():
            option = self.optionobj(name)
            if always is None or name in always or option.default != value or name in cfgOptions :
                self.cfg.set(section,name, option.tostring(value))
        # write the updated ConfigParser to the fileobj.
        self.cfg.write(fileobj)

    def getConfigOption(self, option, default=None):
        warnings.warn('getConfigOption() will go away in a future version of Yum.\n'
                'Please access option values as attributes or using getattr().',
                DeprecationWarning)
        if hasattr(self, option):
            return getattr(self, option)
        return default
    
    

class YumexOptions:

    def __init__(self):
        self.logger = logging.getLogger('yumex.YumexOptions')
        self.settings = self.getYumexConfig()
        self._optparser = OptionParser()
        self.setupParser()
        
    def parseCmdOptions(self):
        self.getCmdlineOptions()
        self.updateSettings()

    def getYumexConfig(self,configfile='/etc/yumex.conf', sec='yumex' ):
        conf = YumexConf()
        parser = ConfigParser()    
        parser.read( configfile )
        conf.populate( parser, sec )
        return conf
    
    def reload(self):
        self.settings = self.getYumexConfig()
        self.updateSettings()
    
    def getArgs(self):
        return self.cmd_args
    
    def setupParser(self):
        parser = self._optparser
        parser.add_option( "-d", "--debug", 
                        action="store_true", dest="debug", default=False, 
                        help="Debug mode" )
        parser.add_option( "-n", "--noauto", 
                        action="store_false", dest="autorefresh", default=True, 
                        help="No automatic refresh af program start" )
        parser.add_option( "", "--noplugins", 
                        action="store_false", dest="plugins", default=True, 
                        help="Disable yum plugins" )
        parser.add_option( "-C", "--usecache", 
                        action="store_true", dest="usecache", default=False, 
                        help="Use Yum cache only, dont update metadata" )

        parser.add_option("-c", "", dest="conffile", action="store", 
                default='/etc/yum.conf', help="yum config file location",
                metavar=' [config file]')
                        
        parser.add_option( "-O", "--fullobsoletion", 
                        action="store_true", dest="fullobsoletion", default=False, 
                        help="Do full obsoletion every time" )
        parser.add_option( "-v", "--version", 
                        action="store_true", dest="version", default=False, 
                        help="Show Yum Extender Version" )
        parser.add_option( "", "--debuglevel", dest="yumdebuglevel", action="store", 
                default=None, help="yum debugging output level", type='int', 
                metavar='[level]' )      
        parser.add_option( "", "--downloadonly", 
                        action="store_true", dest="downloadonly", default=False, 
                        help="Only download packages, dont process them" )
        parser.add_option( "", "--filelist", 
                        action="store_true", dest="filelist", default=False, 
                        help="Download and show filelists for available packages" )
        parser.add_option( "", "--changelog", 
                        action="store_true", dest="changelog", default=False, 
                        help="Download and show changelogs for available packages" )
        parser.add_option( "", "--nothreads", 
                        action="store_true", dest="nothreads", default=False, 
                        help="DEBUG: Option to disable threads in yumex" )
        self.parserInit = True
        
    def getCmdlineOptions( self ):
        """ Handle commmand line options """  
        parser = self._optparser
        ( options, args ) = parser.parse_args()
        self.cmd_options = options
        self.cmd_args = args
        if options.version:
            ver = "Yum Extender : %s " % const.__yumex_version__
            print ver
            sys.exit(0)

    def dump(self):
        self.logger.info( _( "Current Settings :" ) )
        settings = str( self.settings ).split( '\n' )
        for s in settings:
            if not s.startswith( '[' ):
                self.logger.info("    %s" % s )
        
        

    def updateSettings( self ):
        """ update setting with commandline options """
        #options = ['plugins', 'debug', 'usecache', 'fullobsoletion','nolauncher']
        options = ['plugins', 'debug', 'usecache','yumdebuglevel',
                   'fullobsoletion','autorefresh','conffile','downloadonly',
                   'filelist','changelog','nothreads']
        for opt in options:
            self._calcOption(opt)
            
        # Set package colors
        packages.color_normal = self.settings.color_normal
        packages.color_update = self.settings.color_update
        packages.color_install = self.settings.color_install
        packages.color_obsolete = self.settings.color_obsolete
        
    def _calcOption(self,option):
        '''
        Check if a command line option has a diffent value, than
        the default value for the setting.
        if it is the set the setting value to the value from the 
        commandline option.
        '''
        default = None
        cmdopt = getattr( self.cmd_options, option )
        if self.settings.isoption(option):
            optobj = self.settings.optionobj(option)
            default = optobj.default
        if cmdopt != default:
             setattr( self.settings, option,cmdopt)
            
        
    def check_option( self, option ):
        """ Check options in settings or command line"""
        rc = False
        if option == "debug":
            if self.settings.debug or self.cmd_options.debug:
                rc = True
        elif option == "autorefresh":
            if self.settings.autorefresh and not self.cmd_options.noauto:
                rc = True
        elif option == "filelists":
            if self.settings.filelists:
                rc = True
        elif option == "autocleanup":
            if self.settings.autocleanup:
                rc = True
        elif option == "noplugins":
            if self.settings.noplugins or self.cmd_options.noplugins:
                rc = True        
        elif option == "usecache":
            if self.settings.usecache or self.cmd_options.usecache:
                rc = True        
        return rc       
        
def cleanMarkupSting(msg):
    msg = str(msg) # make sure it is a string
    msg = gobject.markup_escape_text(msg)
    #msg = msg.replace('@',' AT ')                        
    #msg = msg.replace('<','[')                        
    #msg = msg.replace('>',']')                        
    return msg
    
