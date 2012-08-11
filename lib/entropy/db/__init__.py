# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework repository database module}.
    Entropy repositories (server and client) are implemented as relational
    databases. Currently, EntropyRepository class is the object that wraps
    sqlite3 database queries and repository logic: there are no more
    abstractions between the two because there is only one implementation
    available at this time. In future, entropy.db will feature more backends
    such as MySQL embedded, SparQL, remote repositories support via TCP socket,
    etc. This will require a new layer between the repository interface now
    offered by EntropyRepository and the underlying data retrieval logic.
    Every repository interface available inherits from EntropyRepository
    class and has to reimplement its own Schema subclass and its get_init
    method (see EntropyRepository documentation for more information).

    I{EntropyRepository} is the sqlite3 implementation of the repository
    interface, as written above.

"""
from entropy.db.sqlite import EntropySQLiteRepository as EntropyRepository
from entropy.db.mysql import EntropyMySQLRepository
from entropy.db.cache import EntropyRepositoryCacher

__all__ = ["EntropyRepository", "EntropyMySQLRepository",
           "EntropyRepositoryCacher"]
