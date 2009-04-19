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

from entropy.output import *
from entropy.const import *
import text_query
from entropy.server.interfaces import Server
from entropy.i18n import _

def query(myopts):

    if not myopts:
        return 10
    cmd = myopts[0]
    myopts = myopts[1:]
    if not myopts and cmd not in ["list","sets"]:
        return 10

    rc = 0
    Entropy = Server()
    dbconn = Entropy.open_server_repository(just_reading = True)

    if cmd == "search":

        # open read only
        count = 0
        for mykeyword in myopts:
            results = dbconn.searchPackages(mykeyword)
            for result in results:
                count += 1
                text_query.print_package_info(
                    result[1],
                    dbconn,
                    clientSearch = True,
                    extended = True,
                    Equo = Entropy
                )

        if not count:
            print_warning(red(" * ")+red("%s." % (_("Nothing found"),) ))
        rc = 0

    elif cmd == "tags":
        search_tagged_packages(myopts, dbconn, Entropy)
    elif cmd == "sets":
        text_query.search_package_sets(myopts, Equo = Entropy)
    elif cmd == "files":
        text_query.search_files(myopts, dbconn = dbconn, Equo = Entropy)
    elif cmd == "belongs":
        text_query.search_belongs(myopts, dbconn = dbconn, Equo = Entropy)
    elif cmd == "description":
        text_query.search_descriptions(myopts, dbconn = dbconn, Equo = Entropy)
    elif cmd == "needed":
        text_query.search_needed_libraries(myopts, dbconn = dbconn,
            Equo = Entropy)
    elif cmd == "depends":
        text_query.search_inverse_dependencies(myopts, dbconn = dbconn,
            Equo = Entropy)
    elif cmd == "eclass":
        text_query.search_eclass(myopts, dbconn = dbconn, Equo = Entropy)
    elif cmd == "list":
        text_query.search_installed_packages(myopts, dbconn = dbconn, Equo = Entropy)
    elif cmd == "changelog":
        text_query.search_changelog(myopts, dbconn = dbconn, Equo = Entropy)

    del Entropy
    return rc


def search_tagged_packages(tags, dbconn, entropy):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Tag Search"),) ))
        print_info(blue("  # ")+bold(entropy.default_repository))

    for tag in tags:
        results = dbconn.searchTaggedPackages(tag, atoms = True)
        for result in results:
            if etpUi['quiet']:
                print dbconn.retrieveAtom(result[1])
            else:
                text_query.print_package_info(result[1], dbconn, Equo = entropy)
        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Keyword"),) )+bold("\t"+tag))
            print_info(blue(" %s:   " % (_("Found"),) )+bold("\t"+str(len(results)))+red(" %s" % (_("entries"),) ))

    return 0