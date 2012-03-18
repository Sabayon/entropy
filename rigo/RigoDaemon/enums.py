# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-3

    B{Entropy Package Manager Rigo Daemon}.

"""

class ActivityStates:
    (
        AVAILABLE,
        NOT_AVAILABLE,
        UPDATING_REPOSITORIES,
        MANAGING_APPLICATIONS,
        UPGRADING_SYSTEM,
        INTERNAL_ROUTINES
    ) = range(6)
