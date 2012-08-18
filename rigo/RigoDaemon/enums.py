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
    ) = list(range(6))

class AppActions:

    """ Application Transaction Actions """

    INSTALL = "install"
    REMOVE = "remove"
    IDLE = "idle"
    UPGRADE = "upgrade"

class AppTransactionStates:

    """ Application Transaction States """

    DOWNLOAD = "download"
    MANAGE = "manage"

class AppTransactionOutcome:

    SUCCESS = "success"
    INTERNAL_ERROR = "internal-error"
    PERMISSION_DENIED = "permission-denied"
    DEPENDENCIES_NOT_FOUND_ERROR = "dependencies-not-found"
    DEPENDENCIES_NOT_REMOVABLE_ERROR = "dependencies-not-removable"
    DEPENDENCIES_COLLISION_ERROR = "dependencies-collision"
    DISK_FULL_ERROR = "disk-full"
    DOWNLOAD_ERROR = "download-error"
    INSTALL_ERROR = "install-error"
    REMOVE_ERROR = "remove-error"
