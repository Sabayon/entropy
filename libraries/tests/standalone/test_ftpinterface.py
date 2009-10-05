# -*- coding: utf-8 -*-
from entropy.transceivers import FtpInterface
from entropy.output import TextInterface, print_generic
text = TextInterface()

ftp = FtpInterface("ftp://", text)
print_generic(ftp.get_file_md5("test.rnd"))
ftp.close()
