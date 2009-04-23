#!/usr/bin/python2

def _(x):
    return x

myopts = []

old_indent_level = 1
for indent_level, name, space_level, desc in myopts:
    if indent_level > old_indent_level:
        print "\n=over\n"*(indent_level-old_indent_level)
        old_indent_level = indent_level
    elif indent_level < old_indent_level:
        print "\n=back\n"*(old_indent_level-indent_level)
        old_indent_level = indent_level
    print """
=item B<%s>

%s"""     % (name, desc,)
