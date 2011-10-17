import os, errno, stat
from entropy.const import etpUi
etpUi['quiet'] = True
from entropy.server.interfaces import Server

srv = Server()
repos = srv.repositories()
atom_cache = set()

for repo_id in repos:
    repo = srv.open_repository(repo_id)
    pkg_ids = repo.listAllPackageIds(order_by="atom")
    for pkg_id in pkg_ids:
        atom = repo.retrieveAtom(pkg_id)
        if atom in atom_cache:
            continue
        content = repo.retrieveContent(pkg_id)
        for path in content:
            try:
                st = os.lstat(path)
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise
                continue
            if stat.S_ISREG(st.st_mode) and (st.st_nlink > 1) and (st.st_size == 0):
                # hard link !
                print(atom)
                atom_cache.add(atom)
                break

srv.shutdown()
