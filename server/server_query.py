# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server}.

"""

from entropy.output import red, bold, darkred, blue, darkgreen, print_info, \
    print_generic, print_warning
from entropy.const import etpConst, etpUi
import text_query
from entropy.server.interfaces import Server
from entropy.i18n import _

def query(myopts):

    if not myopts:
        return 10
    cmd = myopts[0]
    myopts = myopts[1:]
    if not myopts and cmd not in ["list", "sets"]:
        return -10

    rc = -10
    Entropy = Server()
    dbconn = Entropy.open_server_repository(Entropy.default_repository,
        just_reading = True)

    if cmd == "search":

        # open read only
        count = 0
        for mykeyword in myopts:
            results = dbconn.searchPackages(mykeyword, order_by = "atom")
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

    elif cmd == "match":

        # open read only
        count = 0
        for mykeyword in myopts:
            pkg_id, pkg_rc = dbconn.atomMatch(mykeyword)
            if pkg_id == -1:
                continue
            count += 1
            text_query.print_package_info(
                pkg_id,
                dbconn,
                clientSearch = True,
                extended = True,
                Equo = Entropy
            )

        if not count:
            print_warning(red(" * ")+red("%s." % (_("Nothing found"),) ))
        rc = 0

    elif cmd == "tags":
        rc = search_tagged_packages(myopts, dbconn, Entropy)
    elif cmd == "sets":
        rc = text_query.search_package_sets(myopts, Equo = Entropy)
    elif cmd == "files":
        rc = text_query.search_files(myopts, dbconn = dbconn, Equo = Entropy)
    elif cmd == "belongs":
        rc = text_query.search_belongs(myopts, dbconn = dbconn, Equo = Entropy)
    elif cmd == "description":
        text_query.search_descriptions(myopts, dbconn = dbconn, Equo = Entropy)
        rc = 0
    elif cmd == "needed":
        rc = text_query.search_needed_libraries(myopts, dbconn = dbconn,
            Equo = Entropy)
    elif cmd == "revdeps":
        rc = text_query.search_reverse_dependencies(myopts, dbconn = dbconn,
            Equo = Entropy)
    elif cmd == "list":
        rc = text_query.search_installed_packages(myopts, dbconn = dbconn,
            Equo = Entropy)
    elif cmd == "changelog":
        rc = text_query.search_changelog(myopts, dbconn = dbconn, Equo = Entropy)
    elif cmd == "graph":
        complete_graph = False
        if "--complete" in myopts:
            complete_grah = True
            myopts = [x for x in myopts if x != "--complete"]
        rc = text_query.graph_packages(myopts, complete = complete_graph)
    elif cmd == "revgraph":
        complete_graph = False
        if "--complete" in myopts:
            complete_grah = True
            myopts = [x for x in myopts if x != "--complete"]
        rc = text_query.revgraph_packages(myopts, complete = complete_graph)

    del Entropy
    return rc


def search_tagged_packages(tags, dbconn, entropy):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Tag Search"),) ))
        print_info(blue("  # ")+bold(entropy.default_repository))

    key_sorter = lambda x: dbconn.retrieveAtom(x[1])
    for tag in tags:
        results = sorted(dbconn.searchTaggedPackages(tag, atoms = True),
            key = key_sorter)
        for result in results:
            if etpUi['quiet']:
                print_generic(dbconn.retrieveAtom(result[1]))
            else:
                text_query.print_package_info(result[1], dbconn, Equo = entropy)
        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Keyword"),) )+bold("\t"+tag))
            print_info(blue(" %s:   " % (_("Found"),) ) + \
                bold("\t"+str(len(results)))+red(" %s" % (_("entries"),) ))

    return 0
