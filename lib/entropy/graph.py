# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @copyright: Vincenzo Di Massa
    @copyright: 
    @license: GPL-2

    Entropy Graph implementation.
    This module implements a Graph object and a topological sorting algorithm
    based on Tarjan's.

"""
from entropy.misc import Lifo

class GraphNode(object):

    """
    This class represents an item in the Graph. Inside this class you can find
    the GraphNode stored content (through the item() method) and links between
    other GraphNode objects.
    """

    def __init__(self, item):
        """
        GraphNode constructor.

        @param item: the object it is intended to be stored inside this graph
        node.
        @type item: any Python object.
        """
        object.__init__(self)
        self.__item = item
        self.__arches = set()

    def _clear(self):
        """
        Clear the object
        """
        try:
            self.__arches.clear()
        except (NameError, AttributeError):
            pass
        try:
            self.__item = None
        except (NameError, AttributeError):
            pass

    def __str__(self):
        """
        Default string representation.
        """
        repr_str = "\n<GraphNode[item:%s][arches:%s]>\n" % (self.item(),
            [str(x) for x in self.arches()],)
        return repr_str

    def item(self):
        """
        Return item content, object passed to the constructor.

        @return: GraphNode content
        @rtype: Python object
        """
        return self.__item

    def add_arch(self, arch):
        """
        Our lil' graph item feels very lonely. Let's add an arch object to it.
        (GraphArchSet).
        An "arch" object is a topological arch representation.

        @param arch: GraphArchSet instance
        @type arch: GraphArchSet
        @raises AttributeError: if arch is not a GraphArchSet instance
        """
        if not isinstance(arch, GraphArchSet):
            raise AttributeError("GraphArchSet item expected")
        self.__arches.add(arch)

    def remove_arch(self, arch):
        """
        Remove an arch object from this GraphNode instance.
        An "arch" object is a topological arch representation.

        @param arch: GraphArchSet instance
        @type arch: GraphArchSet
        @raises AttributeError: if arch is not a GraphArchSet instance
        """
        if not isinstance(arch, GraphArchSet):
            raise AttributeError("GraphArchSet item expected")
        self.__arches.discard(arch)

    def arches(self):
        """
        Return the currently stored list of arch objects.
        An "arch" object is a topological arch representation.

        @return: list (set) of GraphArchSet objects
        @rtype: set
        """
        return self.__arches

    def is_arch_outgoing(self, arch):
        """
        Determine whether given GraphArchSet object represents an outgoing arch
        of this GraphNode object.

        @return: True, if GraphArchSet passed is an outgoing arch.
        @rtype: bool
        """
        return arch.origin() is self

    def is_arch_coming(self, arch):
        """
        Determine whether given GraphArchSet object represents a coming arch
        of this GraphNode object.

        @return: True, if GraphArchSet passed is a coming arch.
        @rtype: bool
        """
        return self in arch.endpoints()


class GraphArchSet(object):

    """
    This class represents a conceptually improved Graph arch
    (or edge) which connects a starting point "A" to several end-
    points {B,C,D...}.
    The starting point is given at GraphArchSet construction time while
    endpoints can be dynamically removed.
    """

    def __init__(self, starting_point):
        """
        GraphArchSet constructor.

        @param starting_point: a GraphNode instance which represents the
            starting point of the "arch".
        @type starting_point: a GraphNode instance
        """
        if not isinstance(starting_point, GraphNode):
            raise AttributeError("GraphNode item expected")

        object.__init__(self)
        self.__origin = starting_point
        self.__endpoints = set()

    def _clear(self):
        """
        Cleanup the object
        """
        try:
            self.__endpoints.clear()
            del self.__origin
        except (NameError, AttributeError):
            pass

    def __str__(self):
        """
        Default string representation.
        """
        repr_str = "<GraphArchSet[origin:%s][endpoints:%s]>" % (
            repr(self.origin()), self.endpoints(),)
        return repr_str

    def origin(self):
        """
        Return the origin of this GraphArchSet instance (in other words, the
            starting_point object passed to the constructor).
        """
        return self.__origin

    def add_endpoint(self, endpoint):
        """
        Our supercool GraphArchSet can be split infinite times to point to
        multiple GraphNode objects. This methods adds another end-point to
        the arch.

        @param endpoint: a GraphNode instance which represents the
            end-point of the "arch".
        @type endpoint: a GraphNode instance
        """
        if not isinstance(endpoint, GraphNode):
            raise AttributeError("GraphNode item expected")
        self.__endpoints.add(endpoint)

    def remove_endpoint(self, endpoint):
        """
        Our supercool GraphArchSet can be split infinite times to point to
        multiple GraphNode objects. This method removes an existing end-point
        from the arch.
        Beware that, for performance reasons, this method does not check
        if endpoint object (GraphNode previously added with add_endpoint())
        is effectively stored inside, so if endpoint does not exist, nothing
        will happen.

        @param endpoint: a GraphNode instance which represents the
            end-point of the "arch".
        @type endpoint: a GraphNode instance
        """
        if not isinstance(endpoint, GraphNode):
            raise AttributeError("GraphNode item expected")
        self.__endpoints.discard(endpoint)

    def endpoints(self):
        """
        This method returns a frozen copy of the internal end-point list object.

        @return: list (set) of available endpoints
        @rtype: frozenset
        """
        return frozenset(self.__endpoints)


class TopologicalSorter(object):

    """
    This class implements the topological sorting algorithm presented by
    R. E. Tarjan in 1972.
    """

    def __init__(self, adjacency_map):
        """
        TopologicalSorter constructor.

        @param adjacency_map: dict form adjacency map
        @type adjacency_map: dict
        """
        object.__init__(self)
        self.__adjacency_map = adjacency_map
        self.__stack = Lifo()

    def __topological_sort_visit_node(self, node, low, result):
        """
        Internal method, visits a node ad push to stack.
        """
        if node in low:
            return

        num = len(low)
        low[node] = num
        stack_pos = len(self.__stack)
        self.__stack.push(node)

        for successor in self.__adjacency_map[node]:
            self.__topological_sort_visit_node(successor, low, result)
            low[node] = min(low[node], low[successor])

        if num == low[node]:
            component = tuple()
            while len(self.__stack) > stack_pos:
                component += (self.__stack.pop(),)
            result.append(component)
            for item in component:
                low[item] = len(self.__adjacency_map)

    def __strongly_connected_nodes(self):
        """
        Find the strongly connected nodes in a adjacency_map using
        Tarjan's algorithm.

        adjacency_map should be a dictionary mapping node names to
        lists of successor nodes.
        """
        result = []
        low = {}

        for node in self.__adjacency_map:
            self.__topological_sort_visit_node(node, low, result)

        return result


    def __topological_sort(self, graph):
        """
        Effectively executes topological sorting on given graph.
        """

        # initialize count map
        count = dict((node, 0) for node in graph)

        for node in graph:
            for successor in graph[node]:
                count[successor] += 1

        ready_stack = Lifo()
        for node in graph:
            if count[node] == 0:
                ready_stack.push(node)

        dep_level = 1
        result = {}
        while ready_stack.is_filled():

            node = ready_stack.pop()
            result[dep_level] = node
            dep_level += 1

            for successor in graph[node]:
                count[successor] -= 1
                if count[successor] == 0:
                    ready_stack.push(successor)

        return result

    def get_stored_adjacency_map(self):
        """
        Return stored adjacency map used for sorting.

        @return: stored adjacency map
        @rtype: dict
        """
        return self.__adjacency_map

    def sort(self):
        """
        Given an adjacency map, identify strongly connected nodes,
        then perform a topological sort on them.

        @return: sorted graph representation
        @rtype: dict
        """
        # clear stack
        self.__stack.clear()

        components = self.__strongly_connected_nodes()

        node_component = {}
        for component in components:
            for node in component:
                node_component[node] = component

        component_graph = {}
        for node in self.__adjacency_map:
            node_c = node_component[node]
            obj = component_graph.setdefault(node_c, [])
            for successor in self.__adjacency_map[node]:
                successor_c = node_component[successor]
                if node_c != successor_c:
                    obj.append(successor_c)

        return self.__topological_sort(component_graph)


class Graph(object):

    """
    This class represents a Graph object. Elements can be added using the
    add() method and sorted using solve(). This class can also return an
    adjacency map representing the currently stored elements in graph.
    A topological sorting algorithm (using Tarjan's) is used to by solve().
    """

    def __init__(self):
        """
        Graph representation constructor.
        """
        object.__init__(self)
        self.__graph = {}
        self.__archs_map = {}
        self.__graph_map_cache = None

    def destroy(self):
        """
        Cleanup any reference.
        """
        try:
            for obj in self.__graph.values():
                obj._clear()
            self.__graph.clear()
        except (NameError, AttributeError):
            pass
        try:
            for obj in self.__archs_map.values():
                obj._clear()
            self.__archs_map.clear()
        except (NameError, AttributeError):
            pass
        try:
            if self.__graph_map_cache is not None:
                for obj in self.__graph_map_cache.values():
                    obj._clear()
                self.__graph_map_cache.clear()
                self.__graph_map_cache = None
        except (NameError, AttributeError):
            pass

    def __invalidate_cache(self):
        """
        Private method, stay away from here.
        """
        self.__graph_map_cache = None

    def get_node(self, item):
        """
        Return GraphNode instance for added item (through add())

        @param item: Python object to be added to the graph
        @type item: Python object
        @return: GraphNode instance bound to item
        @rtype: entropy.graph.GraphNode
        @raise KeyError: if item is not in Graph
        """
        return self.__graph[item]

    def add(self, item, dependency_items):
        """
        Add arbitrary object to Graph, specifying its dependencies.

        @param item: Python object to be added to the graph
        @type item: Python object
        @param dependency_items: list of items which are dependencies of
            the given item object
        @type dependency_items: set
        """
        self.__invalidate_cache()

        graph_node = self.__graph.setdefault(item, GraphNode(item))
        arch = self.__archs_map.setdefault(graph_node, GraphArchSet(graph_node))
        graph_node.add_arch(arch)

        for dep_item in dependency_items:
            graph_node_dep = self.__graph.setdefault(dep_item,
                GraphNode(dep_item))
            arch.add_endpoint(graph_node_dep)
            graph_node_dep.add_arch(arch)

    def get_adjacency_map(self):
        """
        Return an adjacency map given the current items in Graph.

        @return: adjacency map
        @rtype: dict
        """
        if self.__graph_map_cache is not None:
            return self.__graph_map_cache.copy()

        graph_map = {}
        for node_item in self.__graph.values():

            my_graph_map = set()
            for arch in node_item.arches():
                if node_item.is_arch_outgoing(arch):
                    my_graph_map |= arch.endpoints()

            graph_map[node_item] = my_graph_map

        self.__graph_map_cache = graph_map.copy()
        return graph_map

    def solve_nodes(self):
        """
        This method is equal to solve() but doesn't do any item back-translation
        and just returns the relation between GraphNode objects that can be
        manipulated directly by the caller.

        @return: sorted graph representation (returning GraphNode objects)
        @rtype: dict
        """
        adj_map = self.get_adjacency_map()
        sorter = TopologicalSorter(adj_map)
        return sorter.sort()

    def solve(self):
        """
        Thanks to "R. E. Tarjan" (1972) for the help ;-)
        Serialize the graph and spit out a dependency order.
        Data is returned in map form, where key represents the dependency
        level and value a list of items at that dependency level.

        @return: sorted graph representation
        @rtype: dict
        """
        def trans_vals(node_list):
            return tuple([x.item() for x in node_list])

        sorted_data = self.solve_nodes()
        return dict((x, trans_vals(y),) for x, y in sorted_data.items())

    def raw(self):
        """
        Return all items stored in the graph in raw form (list) without sorting
        them.

        @return: list of items added to Graph
        @rtype: list
        """
        return [x.item() for x in self.__graph.values()]

    def _graph_debug(self):
        """
        This method is used by entropy.debug module and it's not meant for
        general consumption.
        """
        return self.__graph


__all__ = ["Graph"]
