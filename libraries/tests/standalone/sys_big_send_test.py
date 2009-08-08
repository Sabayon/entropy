cmd = 'test:echo %s' % ('c'*90000,)

from entropy.dump import unserialize_string
from entropy.client.interfaces import Client
from entropy.client.services.ugc.commands import Base
from entropy.services.ugc.interfaces import Client as SockClient

cl = Client()
srv = SockClient(cl, Base, ssl = True)
srv.connect('192.168.1.1', 2000)
session = srv.open_session()
srv.transmit('%s %s' % (session, cmd,))
print "cmd answer", srv.receive()
srv.transmit('%s rc' % (session,))
raw_data = srv.receive()
if isinstance(raw_data, basestring):
    raw_data = unserialize_string(raw_data)
print raw_data

srv.close_session(session)
srv.disconnect()

cl.destroy()
raise SystemExit(0)
