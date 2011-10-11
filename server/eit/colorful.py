# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

NOTE: this colorful stuff introduces some unwanted effects.
But it's better than living in a black/white world.
"""
import sys
import argparse

import textwrap as _textwrap

from entropy.output import decolorize

class ColorfulFormatter(argparse.RawDescriptionHelpFormatter):
    """
    This is just a whacky HelpFormatter flavour to add some coloring.
    """

    def _split_lines(self, text, width):
        text = self._whitespace_matcher.sub(' ', text).strip()
        width_span = len(text) - len(decolorize(text))
        return _textwrap.wrap(text, width + width_span)

if sys.hexversion >= 0x3000000:
    str_class = str
else:
    str_class = unicode
class ColorfulStr(str_class):
    """
    This String object has been introduced to fake
    argparse width calculations and allow colorful
    help.
    """
    def __new__(cls, seq):
        return str_class.__new__(cls, seq)

    def __len__(self):
        return len(decolorize(self))
