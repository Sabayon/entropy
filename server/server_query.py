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

    rc = 0
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
        text_query.searchTaggedPackages(myopts, dbconn = dbconn, EquoConnection = Entropy)
    elif cmd == "files":
        text_query.searchFiles(myopts, dbconn = dbconn, EquoConnection = Entropy)
    elif cmd == "belongs":
        text_query.searchBelongs(myopts, dbconn = dbconn, EquoConnection = Entropy)
    elif cmd == "description":
        text_query.searchDescriptions(myopts, dbconn = dbconn, EquoConnection = Entropy)
    elif cmd == "needed":
        text_query.searchNeeded(myopts, dbconn = dbconn, EquoConnection = Entropy)
    elif cmd == "depends":
        text_query.searchDepends(myopts, dbconn = dbconn, EquoConnection = Entropy)
    elif cmd == "eclass":
        text_query.searchEclass(myopts, dbconn = dbconn, EquoConnection = Entropy)

    del Entropy
    return rc
