# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Debug classes}.

"""
import os

from entropy.const import const_debug_write, const_setup_file, \
    const_mkstemp, etpConst

class DebugList(list):

    """
    This class implements a list() object with debug prints using
    entropy.const.const_debug_write
    """

    def __init__(self):
        list.__init__(self)

    def __add__(self, other):
        const_debug_write(__name__, "%s __add__ called: %s" % (self, other,))
        return list.__add__(self, other)

    def __contains__(self, item):
        const_debug_write(__name__, "%s __contains__ called: %s" % (
            self, item,))
        return list.__contains__(self, item)

    def __delattr__(self, name):
        const_debug_write(__name__, "%s __delattr__ called: %s" % (
            self, name,))
        return list.__delattr__(self, name)

    def __delitem__(self, key):
        const_debug_write(__name__, "%s __delitem__ called: %s" % (
            self, key,))
        return list.__delitem__(self, key)

    def __delslice__(self, i, j):
        const_debug_write(__name__, "%s __delslice__ called: %s|%s" % (
            self, i, j,))
        return list.__delslice__(self, i, j)

    def __eq__(self, other):
        const_debug_write(__name__, "%s __eq__ called: %s" % (
            self, other,))
        return list.__eq__(self, other)

    def __ge__(self, other):
        const_debug_write(__name__, "%s __ge__ called: %s" % (
            self, other,))
        return list.__ge__(self, other)

    def __getattribute__(self, name):
        const_debug_write(__name__, "%s __getattribute__ called: %s" % (
            self, name,))
        return list.__getattribute__(self, name)

    def __getitem__(self, key):
        const_debug_write(__name__, "%s __getitem__ called: %s" % (
            self, key,))
        return list.__getitem__(self, key)

    def __gt__(self, other):
        const_debug_write(__name__, "%s __gt__ called: %s" % (
            self, other,))
        return list.__gt__(self, other)

    def __hash__(self):
        const_debug_write(__name__, "%s __hash__ called" % (
            self,))
        return list.__hash__(self)

    def __iadd__(self, other):
        const_debug_write(__name__, "%s __iadd__ called: %s" % (
            self, other,))
        return list.__iadd__(self, other)

    def __imul__(self, other):
        const_debug_write(__name__, "%s __imul__ called: %s" % (
            self, other,))
        return list.__imul__(self, other)

    def __iter__(self):
        const_debug_write(__name__, "%s __iter__ called" % (
            self,))
        return list.__iter__(self)

    def __le__(self, other):
        const_debug_write(__name__, "%s __le__ called: %s" % (
            self, other,))
        return list.__le__(self, other)

    def __len__(self):
        const_debug_write(__name__, "%s len called" % (self,))
        return list.__len__(self)

    def __lt__(self, other):
        const_debug_write(__name__, "%s __lt__ called: %s" % (
            self, other,))
        return list.__lt__(self, other)

    def __mul__(self, other):
        const_debug_write(__name__, "%s __mul__ called: %s" % (
            self, other,))
        return list.__mul__(self, other)

    def __ne__(self, other):
        const_debug_write(__name__, "%s __ne__ called: %s" % (
            self, other,))
        return list.__ne__(self, other)

    def __reversed__(self):
        const_debug_write(__name__, "%s __reversed__ called" % (
            self,))
        return list.__reversed__(self)

    def __setattr__(self, name, value):
        const_debug_write(__name__, "%s __setattr__ called: %s => %s" % (
            self, name, value,))
        return list.__setattr__(self, name, value)

    def __setitem__(self, key, value):
        const_debug_write(__name__, "%s __setitem__ called: %s => %s" % (
            self, key, value,))
        return list.__setitem__(self, key, value)

    def __setslice__(self, i, j, sequence):
        const_debug_write(__name__,
            "%s __setslice__ called: i:%s,j:%s,seq:%s" % (
                self, i, j, sequence,))
        return list.__setslice__(self, i, j, sequence)

    def append(self, item):
        const_debug_write(__name__, "%s append called: %s" % (self, item,))
        return list.append(self, item)

    def count(self, item):
        const_debug_write(__name__, "%s count called: %s" % (self, item,))
        return list.count(self, item)

    def extend(self, other):
        const_debug_write(__name__, "%s extend called: %s" % (self, other,))
        return list.extend(self, other)

    def index(self, item):
        const_debug_write(__name__, "%s index called: %s" % (self, item,))
        return list.index(self, item)

    def insert(self, pos, item):
        const_debug_write(__name__,
            "%s insert called: pos:%s => %s" % (self, pos, item,))
        return list.insert(self, pos, item)

    def pop(self, *args, **kwargs):
        const_debug_write(__name__,
            "%s pop called: %s, %s" % (self, args, kwargs,))
        return list.pop(self, *args, **kwargs)

    def remove(self, elem):
        const_debug_write(__name__, "%s remove called: %s" % (self, elem,))
        return list.remove(self, elem)

    def reverse(self):
        const_debug_write(__name__, "%s reverse called" % (self,))
        return list.reverse(self)

    def sort(self, *args, **kwargs):
        const_debug_write(__name__, "%s sort called: %s, %s" % (
            self, args, kwargs))
        return list.sort(self, *args, **kwargs)


class GraphDrawer(object):

    """
    GraphDrawer is a draw generator for entropy.graph.Graph objects using
    pydot library, which uses Graphviz.
    It requires pydot installed.
    NOTE for packagers: this is debug code included in the entropy core library.
    It doesn't mean you're allowed to include pydot as entropy dependency.
    If you do so, the same class will be wiped out and you'll be fucked ;-)

    """

    def __init__(self, entropy_client, graph):
        """
        GraphDrawer Constructor.

        @param entropy_client: Entropy Client interfaces
        @type entropy_client: entropy.client.interfaces.client.Client
        @param graph: a finalized entropy.graph.Graph object ready to be drawed
        @type graph: entropy.graph.Graph
        """
        self._entropy = entropy_client
        self._entropy_graph = graph
        import pydot
        self._pydot = pydot

    def _generate_pydot(self):

        def _get_name(pkg_match):
            pkg_id, repo_id = pkg_match
            repo = self._entropy.open_repository(repo_id)
            name = "%s::%s,%d" % (repo.retrieveAtom(pkg_id),
                repo_id, pkg_id)
            return name

        graph = self._pydot.Dot(graph_name="Packages",
            graph_type="digraph", suppress_disconnected=True)

        # thanks
        # key = package match
        # value = entropy.graph.GraphNode object
        raw_graph = self._entropy_graph._graph_debug()
        # first add all the nodes
        name_map = {}
        for pkg_match in raw_graph.keys():
            name = _get_name(pkg_match)
            name_map[pkg_match] = name
            node = self._pydot.Node(name)
            graph.add_node(node)
        # now add edges
        for pkg_match, graph_node in raw_graph.items():
            # list of GraphArchSet
            outgoing_arches = [x for x in graph_node.arches() if \
                graph_node.is_arch_outgoing(x)]
            for arch in outgoing_arches:
                arch_pkg_matches = [x.item() for x in arch.endpoints()]
                for arch_pkg_match in arch_pkg_matches:
                    edge = self._pydot.Edge(name_map[pkg_match],
                        name_map[arch_pkg_match])
                    graph.add_edge(edge)

        return graph

    def generate_png(self):
        """
        Generate a PNG from current Graph content.
        """
        graph = self._generate_pydot()
        tmp_fd, tmp_path = const_mkstemp(prefix="entropy.graph",
            suffix=".png")
        os.close(tmp_fd)
        graph.write_png(tmp_path)
        const_setup_file(tmp_path, etpConst['entropygid'], 0o644)
        return tmp_path

    def generate_dot(self):
        """
        Generate RAW dot file that can be used to feed graphviz
        """
        graph = self._generate_pydot()
        tmp_fd, tmp_path = const_mkstemp(prefix="entropy.graph",
            suffix=".dot")
        os.close(tmp_fd)
        graph.write_raw(tmp_path)
        const_setup_file(tmp_path, etpConst['entropygid'], 0o644)
        return tmp_path
