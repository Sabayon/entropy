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
