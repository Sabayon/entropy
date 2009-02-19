import sys
sys.path.insert(0,'../')
from entropy import urlFetcher
url = "http://svn.sabayonlinux.org/entropy/standard/sabayonlinux.org/database/amd64/4/packages.db.bz2"
to = "/tmp/packages.db.bz2"
u = urlFetcher(url, to)
print u.download()
