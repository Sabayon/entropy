# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import sys
import argparse

import textwrap as _textwrap

from entropy.output import decolorize

class ColorfulFormatter(argparse.RawTextHelpFormatter):
    """
    This is just a whacky HelpFormatter flavour to add some coloring.
    """

    def __colors(self, tup_str, orig_str):
        pre_spaces = len(tup_str) - len(tup_str.lstrip())
        post_spaces = len(tup_str) - len(tup_str.rstrip())
        return " "*pre_spaces + orig_str.strip() \
            + " "*post_spaces

    def _format_action(self, action):
        # determine the required width and the entry label
        help_position = min(self._action_max_length + 2,
                            self._max_help_position)
        help_width = self._width - help_position
        action_width = help_position - self._current_indent - 2
        orig_action_header = self._format_action_invocation(action)
        action_header = decolorize(orig_action_header)

        # ho nelp; start on same line and add a final newline
        if not action.help:
            tup = self._current_indent, '', action_header
            action_header = '%*s%s\n' % tup

        # short action name; start on the same line and pad two spaces
        elif len(action_header) <= action_width:
            tup = self._current_indent, '', action_width, action_header
            tup_str = '%*s%-*s  ' % tup
            action_header = self.__colors(tup_str, orig_action_header)
            indent_first = 0

        # long action name; start on the next line
        else:
            tup = self._current_indent, '', action_header
            tup_str = '%*s%-*s  ' % tup
            action_header = self.__colors(tup_str, orig_action_header)
            indent_first = help_position

        # collect the pieces of the action help
        parts = [action_header]

        # if there was help for the action, add lines of help text
        if action.help:
            orig_help_text = self._expand_help(action)
            help_text = decolorize(orig_help_text)
            help_lines = self._split_lines(help_text, help_width)
            orig_help_lines = self._split_lines(orig_help_text, help_width)
            tup_str = '%*s%s' % (indent_first, '', help_lines[0])
            parts.append(self.__colors(tup_str, orig_help_lines[0]) + "\n")
            for idx, line in enumerate(help_lines[1:]):
                tup_str = '%*s%s' % (help_position, '', line)
                parts.append(
                    self.__colors(tup_str, orig_help_lines[idx+1]) + "\n")

        # or add a newline if the description doesn't end with one
        elif not action_header.endswith('\n'):
            parts.append('\n')

        # if there are any sub-actions, add their help as well
        for subaction in self._iter_indented_subactions(action):
            parts.append(self._format_action(subaction))

        # return a single string
        return self._join_parts(parts)
