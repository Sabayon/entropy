#!/usr/bin/python
import os
import sys

os.environ['ETP_GETTEXT_DOMAIN'] = "entropy"

# Entropy imports
sys.path.insert(0, "/usr/lib/entropy/lib")
sys.path.insert(0, "/usr/lib/entropy/client")
sys.path.insert(0, "../lib")
sys.path.insert(0, "../client")

from solo.main import main
sys.argv[0] = "equo"
main()
