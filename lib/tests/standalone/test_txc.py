import tempfile
import os
from entropy.transceivers import EntropyTransceiver

txc = EntropyTransceiver("ssh://user@sabayon.org:~/")
tmp_fd, tmp_path = tempfile.mkstemp()
os.close(tmp_fd)

with open(tmp_path, "w") as tmp_f:
    tmp_f.write("hello"*100)
    tmp_f.flush()

#with txc as handler:
#    print "uploading", tmp_path
#    print handler.upload(tmp_path, "")

with txc as handler:
    print "downloading tmpMCW0qm"
    print handler.download("tmpMCW0qm", ".")
