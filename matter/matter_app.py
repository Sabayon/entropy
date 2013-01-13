#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Matter TinderBox Toolkit}.

"""
import sys
sys.path.insert(0, "/usr/lib/matter")
sys.path.insert(0, "./")

from matter.main import main

if __name__ == "__main__":
    sys.argv[0] = "matter"
    raise SystemExit(main())
