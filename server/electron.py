#!/usr/bin/python
'''
    # DESCRIPTION:
    # enzyme repository manager application

    Copyright (C) 2007-2008 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

import os, sys
sys.path.insert(0,'../libraries')
sys.path.insert(1,'../client')
sys.path.insert(2,'../server')
sys.path.insert(3,'/usr/lib/entropy/client')
sys.path.insert(4,'/usr/lib/entropy/libraries')
sys.path.insert(5,'/usr/lib/entropy/server')
from entropyConstants import *
from outputTools import *
from entropy_i18n import _
import entropyTools
from entropy import RepositoryManager
my = RepositoryManager(community_repo = True)
my.start()
