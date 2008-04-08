#!/usr/bin/python
'''
    # DESCRIPTION:
    # server tools for querying database

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

from outputTools import *
from entropyConstants import *
import text_query
from entropy import ServerInterface

def query(myopts):

    if not myopts:
        return 10
    cmd = myopts[0]
    myopts = myopts[1:]
    if not myopts:
        return 10

    rc = 10
    Entropy = ServerInterface()
    dbconn = Entropy.openServerDatabase(just_reading = True)

    if cmd == "search":

        # open read only
        count = 0
        for mykeyword in myopts:
            results = dbconn.searchPackages(mykeyword)
            for result in results:
                count += 1
                text_query.printPackageInfo(    result[1],
                                                dbconn,
                                                clientSearch = True,
                                                extended = True,
                                                EquoConnection = Entropy
                                            )

        if not count:
            print_warning(red(" * ")+red("Nothing found."))
        rc = 0

    elif cmd == "tags":
        rc = text_query.searchTaggedPackages(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

    elif cmd == "files":
        rc = text_query.searchFiles(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

    elif cmd == "belongs":
        rc = text_query.searchBelongs(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

    elif cmd == "description":
        rc = text_query.searchDescriptions(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

    elif cmd == "needed":
        rc = text_query.searchNeeded(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

    elif myopts[0] == "depends":
        rc = text_query.searchDepends(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

    elif myopts[0] == "eclass":
        rc = text_query.searchEclass(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

    del Entropy
    return rc
