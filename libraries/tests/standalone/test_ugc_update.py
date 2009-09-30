from entropy.client.interfaces import Client
cl = Client()
print(cl.UGC.get_all_downloads("sabayonlinux.org"))
cl.destroy()
raise SystemExit(0)
