# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    I{EntropyRepository} is an abstract class that implements
    most of the EntropyRepository methods using standard SQL.

"""
from entropy.db.skel import EntropyRepositoryBase

class EntropySQLRepository(EntropyRepositoryBase):

    """
    EntropySQLRepository partially implements a SQL based repository
    storage.
    """

    class Schema:

        def get_init(self):
            data = """
                CREATE TABLE baseinfo (
                    idpackage INTEGER PRIMARY KEY AUTOINCREMENT,
                    atom VARCHAR,
                    category VARCHAR,
                    name VARCHAR,
                    version VARCHAR,
                    versiontag VARCHAR,
                    revision INTEGER,
                    branch VARCHAR,
                    slot VARCHAR,
                    license VARCHAR,
                    etpapi INTEGER,
                    trigger INTEGER
                );

                CREATE TABLE extrainfo (
                    idpackage INTEGER PRIMARY KEY,
                    description VARCHAR,
                    homepage VARCHAR,
                    download VARCHAR,
                    size VARCHAR,
                    chost VARCHAR,
                    cflags VARCHAR,
                    cxxflags VARCHAR,
                    digest VARCHAR,
                    datecreation VARCHAR,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );
                CREATE TABLE content (
                    idpackage INTEGER,
                    file VARCHAR,
                    type VARCHAR,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE contentsafety (
                    idpackage INTEGER,
                    file VARCHAR,
                    mtime FLOAT,
                    sha256 VARCHAR,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE provide (
                    idpackage INTEGER,
                    atom VARCHAR,
                    is_default INTEGER DEFAULT 0,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE dependencies (
                    idpackage INTEGER,
                    iddependency INTEGER,
                    type INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE dependenciesreference (
                    iddependency INTEGER PRIMARY KEY AUTOINCREMENT,
                    dependency VARCHAR
                );

                CREATE TABLE conflicts (
                    idpackage INTEGER,
                    conflict VARCHAR,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE mirrorlinks (
                    mirrorname VARCHAR,
                    mirrorlink VARCHAR
                );

                CREATE TABLE sources (
                    idpackage INTEGER,
                    idsource INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE sourcesreference (
                    idsource INTEGER PRIMARY KEY AUTOINCREMENT,
                    source VARCHAR
                );

                CREATE TABLE useflags (
                    idpackage INTEGER,
                    idflag INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE useflagsreference (
                    idflag INTEGER PRIMARY KEY AUTOINCREMENT,
                    flagname VARCHAR
                );

                CREATE TABLE keywords (
                    idpackage INTEGER,
                    idkeyword INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE keywordsreference (
                    idkeyword INTEGER PRIMARY KEY AUTOINCREMENT,
                    keywordname VARCHAR
                );

                CREATE TABLE configprotect (
                    idpackage INTEGER PRIMARY KEY,
                    idprotect INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE configprotectmask (
                    idpackage INTEGER PRIMARY KEY,
                    idprotect INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE configprotectreference (
                    idprotect INTEGER PRIMARY KEY AUTOINCREMENT,
                    protect VARCHAR
                );

                CREATE TABLE systempackages (
                    idpackage INTEGER PRIMARY KEY,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE injected (
                    idpackage INTEGER PRIMARY KEY,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE installedtable (
                    idpackage INTEGER PRIMARY KEY,
                    repositoryname VARCHAR,
                    source INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE sizes (
                    idpackage INTEGER PRIMARY KEY,
                    size INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE counters (
                    counter INTEGER,
                    idpackage INTEGER,
                    branch VARCHAR,
                    PRIMARY KEY(idpackage,branch),
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE trashedcounters (
                    counter INTEGER
                );

                CREATE TABLE needed (
                    idpackage INTEGER,
                    idneeded INTEGER,
                    elfclass INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE neededreference (
                    idneeded INTEGER PRIMARY KEY AUTOINCREMENT,
                    library VARCHAR
                );

                CREATE TABLE provided_libs (
                    idpackage INTEGER,
                    library VARCHAR,
                    path VARCHAR,
                    elfclass INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE treeupdates (
                    repository VARCHAR PRIMARY KEY,
                    digest VARCHAR
                );

                CREATE TABLE treeupdatesactions (
                    idupdate INTEGER PRIMARY KEY AUTOINCREMENT,
                    repository VARCHAR,
                    command VARCHAR,
                    branch VARCHAR,
                    date VARCHAR
                );

                CREATE TABLE licensedata (
                    licensename VARCHAR UNIQUE,
                    text BLOB,
                    compressed INTEGER
                );

                CREATE TABLE licenses_accepted (
                    licensename VARCHAR UNIQUE
                );

                CREATE TABLE triggers (
                    idpackage INTEGER PRIMARY KEY,
                    data BLOB,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE entropy_misc_counters (
                    idtype INTEGER PRIMARY KEY,
                    counter INTEGER
                );

                CREATE TABLE categoriesdescription (
                    category VARCHAR,
                    locale VARCHAR,
                    description VARCHAR
                );

                CREATE TABLE packagesets (
                    setname VARCHAR,
                    dependency VARCHAR
                );

                CREATE TABLE packagechangelogs (
                    category VARCHAR,
                    name VARCHAR,
                    changelog BLOB,
                    PRIMARY KEY (category, name)
                );

                CREATE TABLE automergefiles (
                    idpackage INTEGER,
                    configfile VARCHAR,
                    md5 VARCHAR,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagedesktopmime (
                    idpackage INTEGER,
                    name VARCHAR,
                    mimetype VARCHAR,
                    executable VARCHAR,
                    icon VARCHAR,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagedownloads (
                    idpackage INTEGER,
                    download VARCHAR,
                    type VARCHAR,
                    size INTEGER,
                    disksize INTEGER,
                    md5 VARCHAR,
                    sha1 VARCHAR,
                    sha256 VARCHAR,
                    sha512 VARCHAR,
                    gpg BLOB,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE provided_mime (
                    mimetype VARCHAR,
                    idpackage INTEGER,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagesignatures (
                    idpackage INTEGER PRIMARY KEY,
                    sha1 VARCHAR,
                    sha256 VARCHAR,
                    sha512 VARCHAR,
                    gpg BLOB,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagespmphases (
                    idpackage INTEGER PRIMARY KEY,
                    phases VARCHAR,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagespmrepository (
                    idpackage INTEGER PRIMARY KEY,
                    repository VARCHAR,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE entropy_branch_migration (
                    repository VARCHAR,
                    from_branch VARCHAR,
                    to_branch VARCHAR,
                    post_migration_md5sum VARCHAR,
                    post_upgrade_md5sum VARCHAR,
                    PRIMARY KEY (repository, from_branch, to_branch)
                );

                CREATE TABLE xpakdata (
                    idpackage INTEGER PRIMARY KEY,
                    data BLOB
                );

                CREATE TABLE settings (
                    setting_name VARCHAR,
                    setting_value VARCHAR,
                    PRIMARY KEY(setting_name)
                );

            """
            return data

    @staticmethod
    def update(entropy_client, repository_id, force, gpg):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return EntropyRepositoryBase.update(
            entropy_client, repository_id, force, gpg)

    @staticmethod
    def revision(repository_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return EntropyRepositoryBase.revision(repository_id)

    @staticmethod
    def remote_revision(repository_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return EntropyRepositoryBase.remote_revision(repository_id)
