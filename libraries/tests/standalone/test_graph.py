# -*- coding: utf-8 -*-
# temp unit testing code
if __name__ == "__main__":

    from entropy.graph import Graph
    from entropy.client.interfaces import Client
    cl = Client()

    # test with zillions of atoms
    repo = cl.open_repository("sabayonlinux.org")
    atoms = [x[1] for x in repo.listAllDependencies()]
    atoms = [x for x in atoms if not x.startswith("!")]

    graph = Graph()

    for atom in atoms:

        # match string, translate into (x, y) pointer
        pkg_id, repoid = cl.atom_match(atom)
        if pkg_id == -1:
            continue

        # open matched repisitory and retrieve list of dependencies
        # for pkg_id
        repo = cl.open_repository(repoid)
        my_lame_deps = repo.retrieveDependenciesList(pkg_id)
        my_lame_deps = [x for x in my_lame_deps if not x.startswith("!")]

        # match every dependency and build a raw list of dependencies
        atom_deps_list = set()
        for lame_dep in my_lame_deps:
            dep_pkg_id, dep_repoid = cl.atom_match(lame_dep)
            if dep_pkg_id == -1:
                continue # lame thing
            atom_deps_list.add((dep_pkg_id, dep_repoid,))

        # eventually add atom (it's x,y pointer) and its deps to graph
        graph.add((pkg_id, repoid,), atom_deps_list)

    # now print our adjacency map
    adj_map = graph.get_adjacency_map()
    print "=" * 20
    print "adjacency map:"
    for pkg in sorted(adj_map):
        deps = '\n\t'.join([str(x) for x in adj_map[pkg]])
        if not deps:
            deps = 'no dependencies'
        else:
            deps = "\n\t" + deps
        print pkg, "=>", deps
    print "=" * 20

    print "solving:"
    sorted_map = graph.solve()
    for dep_level in sorted(sorted_map, reverse = True):
        print dep_level, sorted_map[dep_level], "{",
        for pkg_id, repoid in sorted_map[dep_level]:
            repo = cl.open_repository(repoid)
            print repo.retrieveAtom(pkg_id),
        print "}"
    print "=" * 20

    cl.destroy()
    raise SystemExit(0)