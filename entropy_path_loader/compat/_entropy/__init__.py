# -*- coding: utf-8 -*-
"""

    @author: Slawomir Nizio <slawomir.nizio@sabayon.org>
    @contact: lxnay@sabayon.org, slawomir.nizio@sabayon.org
    @copyright: Slawomir Nizio
    @license: GPL-2

    B{Module to provide _entropy namespace}.

    When installed, internal modules go into B{_entropy}. This provides it for
    running from the checkout.
"""
import sys

import solo
sys.modules['_entropy.solo'] = solo

import magneto
sys.modules['_entropy.magneto'] = magneto

import eit
sys.modules['_entropy.eit'] = eit

import matter
sys.modules['_entropy.matter'] = matter
