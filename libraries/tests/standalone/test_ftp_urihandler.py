import sys, os
sys.path.insert(0, "../../libraries")
from entropy.transceivers import EntropyTransceiver

txc = EntropyTransceiver("uri://")
# txc.set_speed_limit(35)
txc.set_silent(False)
txc.set_verbosity(True)
handler = txc.swallow()
print handler
print "listing", handler.list_content(".")
print "listing meta", handler.list_content_metadata(".")
print "pushing keep alive", handler.keep_alive()
print "trying to delete test.rnd", handler.is_path_available("test.rnd"), handler.delete("test.rnd")
print "trying to upload test.rnd", handler.upload("test.rnd", "test.rnd")
print "getting md5 of test.rnd", handler.get_md5("test.rnd")
print "downloading test.rnd", handler.download("test.rnd", "test.rnd_down"), os.path.isfile("test.rnd_down")
print "renaming test.rnd", handler.rename("test.rnd", "test.rnd2")
print "checking if test.rnd2 is available", handler.is_path_available("test.rnd2"), "old one =>", handler.is_path_available("test.rnd")
print "deleting test.rnd2", handler.delete("test.rnd2"), handler.is_path_available("test.rnd2")
print "bye bye", handler.close()
