# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Debug classes}.

"""
from entropy.const import const_debug_write

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
        return list.__setitem__(self, key, value)

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

