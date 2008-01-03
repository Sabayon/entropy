#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo repositories handling library

    Copyright (C) 2007-2008 Fabio Erculiani

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

########################################################
####
##   Repositories Tools
#

from entropyConstants import *
from outputTools import *
import exceptionTools
from entropy import EquoInterface
Equo = EquoInterface(noclientdb = True)

def repositories(options):

    # Options available for all the packages submodules
    myopts = options[1:]
    equoRequestForceUpdate = False
    rc = 0
    for opt in myopts:
        if (opt == "--force"):
            equoRequestForceUpdate = True

    if (options[0] == "update"):
        rc = do_sync(forceUpdate = equoRequestForceUpdate)
    elif (options[0] == "status"):
        for repo in etpRepositories:
            showRepositoryInfo(repo)
    elif (options[0] == "repoinfo"):
        showRepositories()
    else:
        rc = -10
    return rc

# this function shows a list of enabled repositories
def showRepositories():
    print_info(darkred(" * ")+darkgreen("Active Repositories:"))
    repoNumber = 0
    for repo in etpRepositories:
        repoNumber += 1
        print_info(blue("\t#"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
        sourcecount = 0
        for pkgrepo in etpRepositories[repo]['packages']:
            sourcecount += 1
            print_info(red("\t\tPackages Mirror #"+str(sourcecount)+" : ")+darkgreen(pkgrepo))
        print_info(red("\t\tDatabase URL: ")+darkgreen(etpRepositories[repo]['database']))
        print_info(red("\t\tRepository name: ")+bold(repo))
        print_info(red("\t\tRepository database path: ")+blue(etpRepositories[repo]['dbpath']))
    return 0

def showRepositoryInfo(reponame):
    repoNumber = 0
    for repo in etpRepositories:
        repoNumber += 1
        if repo == reponame:
            break
    print_info(blue("#"+str(repoNumber))+bold(" "+etpRepositories[reponame]['description']))
    if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']):
        status = "active"
    else:
        status = "never synced"
    print_info(darkgreen("\tStatus: ")+darkred(status))
    urlcount = 0
    for repourl in etpRepositories[reponame]['packages'][::-1]:
        urlcount += 1
        print_info(red("\tPackages URL #"+str(urlcount)+": ")+darkgreen(repourl))
    print_info(red("\tDatabase URL: ")+darkgreen(etpRepositories[reponame]['database']))
    print_info(red("\tRepository name: ")+bold(reponame))
    print_info(red("\tRepository database path: ")+blue(etpRepositories[reponame]['dbpath']))
    revision = Equo.get_repository_revision(reponame)
    mhash = Equo.get_repository_db_file_checksum(reponame)

    print_info(red("\tRepository database checksum: ")+mhash)
    print_info(red("\tRepository revision: ")+darkgreen(str(revision)))
    return 0


def do_sync(reponames = [], forceUpdate = False):

    # load repository class
    try:
        repoConn = Equo.Repositories(reponames, forceUpdate)
    except exceptionTools.PermissionDenied:
        print_error(red("\t You must run this application as root."))
        return 1
    except exceptionTools.MissingParameter:
        print_error(darkred(" * ")+red("No repositories specified in ")+etpConst['repositoriesconf'])
        return 127
    except exceptionTools.OnlineMirrorError:
        print_error(darkred(" @@ ")+red("You are not connected to the Internet. You should."))
        return 126
    except Exception, e:
        print_error(darkred(" @@ ")+red("Unhandled exception: %s" % (str(e),)))
        return 2

    rc = repoConn.sync()
    return rc


