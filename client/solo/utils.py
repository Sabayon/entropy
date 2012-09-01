# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import codecs

from entropy.const import etpConst
from entropy.output import print_generic, darkgreen, decolorize


def read_client_release():
    """
    Read Entropy Command Line Client release.

    @rtype: None
    @return: None
    """
    # handle Entropy Version
    revision_file = "../client/revision"
    if not os.path.isfile(revision_file):
        revision_file = os.path.join(etpConst['installdir'],
            'client/revision')
    if os.path.isfile(revision_file) and \
        os.access(revision_file, os.R_OK):

        enc = etpConst['conf_encoding']
        with codecs.open(revision_file, "r", encoding=enc) \
                as rev_f:
            myrev = rev_f.readline().strip()
            return myrev

    return "0"

def print_table(lines_data, cell_spacing = 2, cell_padding = 0,
    side_color = darkgreen):
    """
    Print a table composed by len(lines_data[i]) columns and len(lines_data)
    rows.

    @param lines_data: list of row data
    @type lines_data: list
    @keyword cell_spacing: cell spacing
    @type cell_spacing: int
    @keyword cell_padding: cell padding
    @type cell_padding: int
    @keyword side_color: colorization callback function
    @type side_color: callable
    """
    column_sizes = {}
    padding_side = int((cell_padding / 2))
    col_n = 0
    for cols in lines_data:
        if not isinstance(cols, (list, tuple)):
            # can be a plain string
            continue
        col_n = 0
        for cell in cols:
            cell_len = len(" "*padding_side + decolorize(cell.split("\n")[0]) \
                 + " "*padding_side)
            cur_len = column_sizes.get(col_n)
            if cur_len is None:
                column_sizes[col_n] = cell_len
            elif cur_len < cell_len:
                column_sizes[col_n] = cell_len
            col_n += 1

    # now actually print
    if col_n > 0:
        column_sizes[col_n - 1] = 0
    for cols in lines_data:
        print_generic(side_color(">>") + " ", end = " ")
        if isinstance(cols, (list, tuple)):
            col_n = 0
            for cell in cols:
                max_len = column_sizes[col_n]
                cell = " "*padding_side + cell + " "*padding_side
                delta_len = max_len - len(decolorize(cell.split("\n")[0])) + \
                    cell_spacing
                if col_n == (len(cols) - 1):
                    print_generic(cell)
                else:
                    print_generic(cell, end = " "*delta_len)
                col_n += 1
        else:
            print_generic(cols)
