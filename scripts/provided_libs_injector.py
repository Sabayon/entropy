from entropy.client.interfaces import Client
cl = Client()

spm = cl.Spm()
dbconn = cl.clientDbconn

count = 0
pkgs = dbconn.listAllIdpackages()
total = len(pkgs)
for idpackage in pkgs:
    count += 1
    print "doing", count, "/", total, dbconn.retrieveAtom(idpackage)
    content = dbconn.retrieveContent(idpackage, extended = True, formatted = True)
    provided_libs = spm._extract_pkg_metadata_provided_libs("/", content)
    dbconn.removeProvidedLibraries(idpackage)
    dbconn.insertProvidedLibraries(idpackage, provided_libs)

cl.destroy()
raise SystemExit(0)

