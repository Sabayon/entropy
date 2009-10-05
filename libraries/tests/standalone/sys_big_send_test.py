# -*- coding: utf-8 -*-
cmd = 'test:echo %s' % ('c'*90000,)

from entropy.const import const_get_stringtype
from entropy.output import print_generic
from entropy.dump import unserialize_string
from entropy.client.interfaces import Client
from entropy.client.services.ugc.commands import Base
from entropy.services.ugc.interfaces import Client as SockClient

cl = Client()
srv = SockClient(cl, Base, ssl = True)
srv.connect('192.168.1.1', 2000)
session = srv.open_session()
srv.transmit('%s %s' % (session, cmd,))
print_generic("cmd answer", srv.receive())
srv.transmit('%s rc' % (session,))
raw_data = srv.receive()
if isinstance(raw_data, const_get_stringtype):
    raw_data = unserialize_string(raw_data)
print_generic(raw_data)

srv.close_session(session)
srv.disconnect()

cl.destroy()
raise SystemExit(0)
