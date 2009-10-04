#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys

def _(x):
    return x

myopts = []

old_indent_level = 1
for indent_level, name, space_level, desc in myopts:
    if indent_level > old_indent_level:
        sys.stdout.write("\n=over\n"*(indent_level-old_indent_level) + "\n")
        old_indent_level = indent_level
    elif indent_level < old_indent_level:
        sys.stdout.write("\n=back\n"*(old_indent_level-indent_level) + "\n")
        old_indent_level = indent_level
    sys.stdout.write("""
=item B<%s>

%s
""" % (name, desc,))
