import sys
sys.argv.append("--debug")
from entropy.client.interfaces import Client
cl = Client()
data = ['app-foo/foo']
cl.UGC.add_download_stats('sabayonlinux.org', data)
cl.destroy()
raise SystemExit(0)
