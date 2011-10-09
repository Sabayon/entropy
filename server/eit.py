#!/usr/bin/python2
import sys

# Entropy imports
sys.path.insert(0, "/usr/lib/entropy/libraries")
sys.path.insert(0, "/usr/lib/entropy/client")
sys.path.insert(0, "/usr/lib/entropy/server")
sys.path.insert(0, "../libraries")
sys.path.insert(0, "../server")
sys.path.insert(0, "../client")

from eit.main import main
sys.argv[0] = "eit"
main()
