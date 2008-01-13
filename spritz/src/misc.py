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

#from yum.config import *

# Use iniparse if it exist, else use Python ConfigParser
try:
    from iniparse.compat import ConfigParser,SafeConfigParser
except:
    from ConfigParser import ConfigParser,SafeConfigParser
    
from optparse import OptionParser
from i18n import _
#import yum.Errors as Errors
#from yum.repos import RepoStorage
import packages


class const:
    ''' This Class contains all the Constants in Yumex'''
    __spritz_version__   = "0.2"
    # Paths
    MAIN_PATH = os.path.abspath( os.path.dirname( sys.argv[0] ) );
    GLADE_FILE = MAIN_PATH+'/spritz.glade'
    if MAIN_PATH == '/usr/lib/entropy/spritz':
        PIXMAPS_PATH = '/usr/share/pixmaps/spritz'
    else:
        PIXMAPS_PATH = MAIN_PATH+'/../gfx'

    # package categories
    PACKAGE_CATEGORIES = [
        "None",
        "Groups",
        "RPM Groups",
        "Age"]

    YUM_PID_FILE = '/var/run/equo.pid'
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
           (('Spritz Package Manager - %s' % __spritz_version__),
           ('Copyright 2008','Fabio Erculiani')),

           (_("Programming:"),
           ("Fabio Erculiani",)),

           (_("Yum Extender Programmers:"),
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


           (_("Dedicated to:"),
                ("Sergio Erculiani",)
           )

          )

class SpritzQueue:
    def __init__(self):
        self.logger = logging.getLogger('yumex.YumexQueue')
        self.packages = {}
        self.packages['i'] = []
        self.packages['u'] = []
        self.packages['r'] = []
        self.groups = {}
        self.groups['i'] = []
        self.groups['r'] = []
        self.Entropy = None
        self.etpbase = None
        self.pkgView = None
        self.queueView = None

    def connect_objects(self, EquoConnection, etpbase, pkgView, queueView):
        self.Entropy = EquoConnection
        self.etpbase = etpbase
        self.pkgView = pkgView
        self.queueView = queueView

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

    def add(self, pkgs):

        one = False
        if type(pkgs) is not list:
            one = True
            pkgs = [pkgs]

        action = [pkgs[0].action]
        if action[0] in ("u","i"): # update/install

            action = ["u","i"]
            tmpqueue = [x for x in pkgs if x not in self.packages['u']+self.packages['i']]
            xlist = [x.matched_atom for x in self.packages['u']+self.packages['i']+tmpqueue]
            status = self.elaborateInstall(pkgs,xlist,action,False)
            return status,0

        else: # remove

            if one:
                status = self.checkSystemPackage(pkgs[0])
                if not status:
                    return -2,1

            tmpqueue = [x for x in pkgs if x not in self.packages[action[0]]]
            xlist = [x.matched_atom[0] for x in self.packages[action[0]]+tmpqueue]
            self.elaborateRemoval(pkgs,xlist,action[0],False)
            return 0,1

    def elaborateInstall(self, pkgs, xlist, actions, deep_deps):
        (runQueue, removalQueue, status) = self.Entropy.retrieveInstallQueue(xlist,False,deep_deps)
        if status == 0:
            # runQueue
            if runQueue:
                for dep_pkg in self.etpbase.getPackages('updates')+self.etpbase.getPackages('available'):
                    for matched_atom in runQueue:
                        if (dep_pkg.matched_atom == matched_atom) and (dep_pkg not in self.packages[actions[0]]+self.packages[actions[1]]):
                            if dep_pkg not in pkgs:
                                dep_pkg.set_select(True)
                                dep_pkg.queued = dep_pkg.action
                            self.packages[dep_pkg.action].append(dep_pkg)
            # removalQueue
            if removalQueue:
                for rem_pkg in self.etpbase.getPackages('installed'):
                    for matched_atom in removalQueue:
                        if rem_pkg.matched_atom == (matched_atom,0):
                            if rem_pkg not in pkgs:
                                rem_pkg.set_select(False)
                                rem_pkg.queued = rem_pkg.action
                            self.packages['r'].append(rem_pkg)
        return status

    def elaborateRemoval(self, pkgs, list, action, nodeps):
        if nodeps:
            return
        removalQueue = self.Entropy.retrieveRemovalQueue(list)
        if removalQueue:
            for rem_pkg in self.etpbase.getPackages('installed'):
                for matched_atom in removalQueue:
                    if rem_pkg.matched_atom == (matched_atom,0):
                        if rem_pkg not in pkgs:
                            rem_pkg.set_select(False)
                            rem_pkg.queued = rem_pkg.action
                        self.packages[rem_pkg.action].append(rem_pkg)


    def checkSystemPackage(self, pkg):
        # check if it's a system package
        valid = self.Entropy.validatePackageRemoval(pkg.matched_atom[0])
        if not valid:
            pkg.set_select(not pkg.selected)
            pkg.queued = None
        return valid

    def remove(self, pkgs):

        one = False
        if type(pkgs) is not list:
            one = True
            pkgs = [pkgs]

        action = [pkgs[0].action]
        if action[0] in ("u","i"): # update/install

            action = ["u","i"]

            for r_pkg in pkgs:
                if r_pkg in self.packages['u']:
                    self.packages['u'].remove( r_pkg )
                if r_pkg in self.packages['i']:
                    self.packages['i'].remove( r_pkg )
            xlist = [x.matched_atom for x in self.packages['u']+self.packages['i']]
            status = self.elaborateInstall(pkgs,xlist,action,False)
            for r_pkg in pkgs:
                if r_pkg in self.packages['u']+self.packages['i']:
                    r_pkg.set_select(not r_pkg.selected)
                    r_pkg.queued = r_pkg.action


            return status,0

        else:

            for r_pkg in pkgs:
                if r_pkg in self.packages[action[0]]:
                    self.packages[action[0]].remove( pkgs[0] )
            tmpdata = self.packages[action[0]][:]
            xlist = [x.matched_atom[0] for x in self.packages[action[0]]]
            self.elaborateRemoval(pkgs,xlist,action[0],False)
            for rem_pkg in tmpdata:
                if rem_pkg not in self.packages[action[0]]:
                    # disable
                    rem_pkg.set_select(not rem_pkg.selected)
                    rem_pkg.action = None
                    rem_pkg.queued = rem_pkg.action
            return 0,1



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
        except:
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
        except:
            return {}


class YumexConf:
    """ Yum Extender Config Setting"""
    autorefresh = True
    recentdays = 14
    debug = False
    plugins = True
    usecache = False
    proxy = ""
    font_console = 'Monospace 8'
    font_pkgdesc = 'Monospace 8'
    color_console = '#68228B'
    color_pkgdesc = '#68228B'
    color_install = 'darkgreen'
    color_update = 'red'
    color_normal = 'black'
    color_obsolete = 'blue'
    filelist = True
    changelog = False
    disable_repo_page = False
    branding_title = 'Spritz Package Manager'

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


class SpritzOptions:

    def __init__(self):
        self.logger = logging.getLogger('yumex.YumexOptions')
        self._optparser = OptionParser()
        self.setupParser()

    def parseCmdOptions(self):
        self.getCmdlineOptions()

    def getYumexConfig(self,configfile='/etc/spritz.conf', sec='spritz' ):
        conf = YumexConf()
        parser = ConfigParser()    
        parser.read( configfile )
        conf.populate( parser, sec )
        return conf

    def reload(self):
        self.settings = self.getYumexConfig()

    def getArgs(self):
        return self.cmd_args

    def setupParser(self):
        parser = self._optparser
        parser.add_option( "-d", "--debug", 
                        action="store_true", dest="debug", default=False, 
                        help="Debug mode" )
        self.parserInit = True

    def getCmdlineOptions( self ):
        """ Handle commmand line options """
        parser = self._optparser
        ( options, args ) = parser.parse_args()
        self.cmd_options = options
        self.cmd_args = args

    def dump(self):
        self.logger.info( _( "Current Settings :" ) )
        settings = str( self.settings ).split( '\n' )
        for s in settings:
            if not s.startswith( '[' ):
                self.logger.info("    %s" % s )

    def check_option( self, option ):
        """ Check options in settings or command line"""
        rc = False
        if option == "debug":
            if self.settings.debug or self.cmd_options.debug:
                rc = True
        return rc

def cleanMarkupSting(msg):
    msg = str(msg) # make sure it is a string
    msg = gobject.markup_escape_text(msg)
    #msg = msg.replace('@',' AT ')
    #msg = msg.replace('<','[')
    #msg = msg.replace('>',']')
    return msg

class fakeoutfile:
    """
    A fake output file object.  It sends output to a GTK TextView widget,
    and if asked for a file number, returns one set on instance creation
    """

    def __init__(self, fn):
        self.fn = fn

    def close(self):
        pass

    def flush(self):
        self.close()

    def fileno(self):
        return self.fn

    def isatty(self):
        return False

    def read(self, a):
        return ''

    def readline(self):
        return ''

    def readlines(self):
        return []

    def write(self, s):
        os.write(self.fn,s)
        #sys.stdout.write(s+"\n")

    def write_line(self, s):
        self.write(s)

    def writelines(self, l):
        for s in l:
            self.write(s)

    def seek(self, a):
        raise IOError, (29, 'Illegal seek')

    def tell(self):
        raise IOError, (29, 'Illegal seek')

    def truncate(self):
        self.tell()

class fakeinfile:
    """
    A fake input file object.  It receives input from a GTK TextView widget,
    and if asked for a file number, returns one set on instance creation
    """

    def __init__(self, fn):
        self.fn = fn
    def close(self): pass
    flush = close
    def fileno(self):    return self.fn
    def isatty(self):    return False
    def read(self, a):   return self.readline()
    def readline(self): ## just a fake
        return os.read(self.fn,2048)
    def readlines(self): return []
    def write(self, s):  return None
    def writelines(self, l): return None
    def seek(self, a):   raise IOError, (29, 'Illegal seek')
    def tell(self):      raise IOError, (29, 'Illegal seek')
    truncate = tell

