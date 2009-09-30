from entropy.transceivers import FtpInterface
from entropy.output import TextInterface
text = TextInterface()

ftp = FtpInterface("ftp://", text)
print(ftp.get_file_md5("test.rnd"))
ftp.close()
