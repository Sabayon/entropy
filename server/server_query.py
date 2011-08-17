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
    entropy_server = None

    try:
        entropy_server = Server()
        if cmd == "search":

            for repository_id in entropy_server.repositories():
                repo_db = entropy_server.open_repository(repository_id)
                count = 0
                for mykeyword in myopts:
                    results = repo_db.searchPackages(mykeyword, order_by = "atom")
                    for result in results:
                        count += 1
                        text_query.print_package_info(
                            result[1],
                            entropy_server,
                            repo_db,
                            installed_search = True,
                            extended = True,
                            quiet = etpUi['quiet']
                        )

                if (not count) and (not etpUi['quiet']):
                    print_warning(red(" * ")+red("%s." % (_("Nothing found"),) ))
            rc = 0

        elif cmd == "match":

            # open read only
            for repository_id in entropy_server.repositories():
                repo_db = entropy_server.open_repository(repository_id)
                count = 0
                for mykeyword in myopts:
                    pkg_id, pkg_rc = repo_db.atomMatch(mykeyword)
                    if pkg_id == -1:
                        continue
                    count += 1
                    text_query.print_package_info(
                        pkg_id,
                        entropy_server,
                        repo_db,
                        installed_search = True,
                        extended = True,
                        quiet = etpUi['quiet']
                    )

                if (not count) and (not etpUi['quiet']):
                    print_warning(red(" * ")+red("%s." % (_("Nothing found"),) ))
                rc = 0

        elif cmd == "tags":
            rc = 0
            for repository_id in entropy_server.repositories():
                repo_db = entropy_server.open_repository(repository_id)
                if search_tagged_packages(myopts, entropy_server, repo_db) != 0:
                    rc = 1
        elif cmd == "sets":
            rc = text_query.search_package_sets(myopts, entropy_server)
        elif cmd == "files":
            rc = 0
            for repository_id in entropy_server.repositories():
                repo_db = entropy_server.open_repository(repository_id)
                if text_query.search_files(myopts, entropy_server, repo_db) != 0:
                    rc = 1
        elif cmd == "belongs":
            rc = 0
            for repository_id in entropy_server.repositories():
                repo_db = entropy_server.open_repository(repository_id)
                if text_query.search_belongs(myopts, entropy_server, repo_db) != 0:
                    rc = 1
        elif cmd == "description":
            rc = 0
            for repository_id in entropy_server.repositories():
                repo_db = entropy_server.open_repository(repository_id)
                if text_query.search_descriptions(myopts, entropy_server, repo_db) != 0:
                    rc = 1
        elif cmd == "needed":
            rc = 0
            for repository_id in entropy_server.repositories():
                repo_db = entropy_server.open_repository(repository_id)
                if text_query.search_needed_libraries(myopts, entropy_server, repo_db) != 0:
                    rc = 1
        elif cmd == "revdeps":
            rc = 0
            for dependency in myopts:
                for repository_id in entropy_server.repositories():
                    repo_db = entropy_server.open_repository(repository_id)
                    pkg_id, pkg_rc = repo_db.atomMatch(dependency)
                    if pkg_id != -1:
                        if text_query.search_reverse_dependencies([dependency],
                                entropy_server, repo_db) != 0:
                            rc = 1
        elif cmd == "list":
            rc = 0
            for repository_id in entropy_server.repositories():
                if myopts and (repository_id not in myopts):
                    continue
                repo_db = entropy_server.open_repository(repository_id)
                if text_query.list_packages(entropy_server, repo_db) != 0:
                    rc = 1
        elif cmd == "changelog":
            rc = 0
            for repository_id in entropy_server.repositories():
                repo_db = entropy_server.open_repository(repository_id)
                if text_query.search_changelog(myopts, entropy_server, repo_db) != 0:
                    rc = 1
        elif cmd == "graph":
            complete_graph = False
            if "--complete" in myopts:
                complete_grah = True
                myopts = [x for x in myopts if x != "--complete"]
            rc = text_query.graph_packages(myopts, entropy_server,
                complete = complete_graph,
                repository_ids = entropy_server.repositories())
        elif cmd == "revgraph":
            complete_graph = False
            if "--complete" in myopts:
                complete_grah = True
                myopts = [x for x in myopts if x != "--complete"]
            rc = text_query.revgraph_packages(myopts, entropy_server,
                complete = complete_graph,
                repository_ids = entropy_server.repositories())
    finally:
        if entropy_server is not None:
            entropy_server.shutdown()

    return rc


def search_tagged_packages(tags, entropy, dbconn):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Tag Search"),) ))
        print_info(blue("  # ")+bold(entropy.repository()))

    key_sorter = lambda x: dbconn.retrieveAtom(x[1])
    for tag in tags:
        results = sorted(dbconn.searchTaggedPackages(tag, atoms = True),
            key = key_sorter)
        for result in results:
            if etpUi['quiet']:
                print_generic(dbconn.retrieveAtom(result[1]))
            else:
                text_query.print_package_info(result[1], entropy, dbconn,
                    quiet = False)
        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Keyword"),) )+bold("\t"+tag))
            print_info(blue(" %s:   " % (_("Found"),) ) + \
                bold("\t"+str(len(results)))+red(" %s" % (_("entries"),) ))

    return 0
