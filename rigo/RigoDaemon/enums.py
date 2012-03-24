# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-3

    B{Entropy Package Manager Rigo Daemon}.

"""

class ActivityStates:

    class BusyError(Exception):
        """
        Cannot acknowledge a Local Activity change.
        """

    class SameError(Exception):
        """
        Trying to switch to the same active Activity.
        """

    class AlreadyAvailableError(Exception):
        """
        Cannot acknowledge a Local Activity change to
        "AVAILABLE" state, because we're already ready.
        """

    class UnbusyFromDifferentActivity(Exception):
        """
        Unbusy request from different activity.
        """

    (
        AVAILABLE,
        NOT_AVAILABLE,
        UPDATING_REPOSITORIES,
        MANAGING_APPLICATIONS,
        UPGRADING_SYSTEM,
        INTERNAL_ROUTINES
    ) = range(6)

class AppActions:
    INSTALL = "install"
    REMOVE = "remove"
    IDLE = "idle"
