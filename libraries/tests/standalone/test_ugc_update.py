# -*- coding: utf-8 -*-
from entropy.output import print_generic
from entropy.client.interfaces import Client
cl = Client()
print_generic(cl.UGC.get_all_downloads("sabayonlinux.org"))
cl.destroy()
raise SystemExit(0)
