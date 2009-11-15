from entropy.server.interfaces import Server
srv = Server()
#print srv.MirrorsService.get_remote_branches()
#print srv.MirrorsService.read_remote_file_in_branches("packages.db.revision")
#print srv.MirrorsService.lock_mirrors()
#print srv.MirrorsService.lock_mirrors(lock=False)
#print srv.MirrorsService.lock_mirrors_for_download()
#print srv.MirrorsService.lock_mirrors_for_download(lock = False)
#print srv.MirrorsService.get_remote_databases_status()
#print srv.MirrorsService.get_mirrors_lock()
#for uri in srv.get_remote_mirrors("community1"):
#    print srv.MirrorsService.mirror_lock_check(uri)
#print srv.MirrorsService.read_notice_board()
#for uri in srv.get_remote_mirrors("community1"):
#    txc = srv.Transceiver(uri)
#    with txc as handler:
#        print srv.MirrorsService._calculate_remote_package_files(uri, "4", handler)
for uri in srv.get_remote_mirrors("community1"):
    txc = srv.Transceiver(uri)
    with txc as handler:
        print srv.MirrorsService.download_package(uri, "packages/amd64/4/app-admin:equo-0.23.8~0.tbz2")
srv.destroy()
raise SystemExit(0)
