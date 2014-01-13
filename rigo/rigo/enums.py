# -*- coding: utf-8 -*-
"""
Copyright (C) 2009 Canonical
Copyright (C) 2012 Fabio Erculiani

Authors:
  Michael Vogt
  Fabio Erculiani

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; version 3.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""

import os
from entropy.i18n import _

SOFTWARE_CENTER_PKGNAME = 'rigo'
SOFTWARE_CENTER_NAME_KEYRING = "Rigo Browser"

# icons
class Icons:
    APP_ICON_SIZE = 48

    FALLBACK = "applications-other"
    MISSING_APP = FALLBACK
    MISSING_PKG = "dialog-question"   # XXX: Not used?
    GENERIC_MISSING = "gtk-missing-image"
    INSTALLED_OVERLAY = "rigo-installed"
    CONFIGURATION_FILE = "text-x-generic"
    REPOSITORY = "repo"
    GROUPS = "applications-other"

# application actions
class AppActions:
    INSTALL = "install"
    REMOVE = "remove"
    IDLE = "idle"
    UPGRADE = "upgrade"

from .version import VERSION, DISTRO, RELEASE, CODENAME
USER_AGENT="Entropy Rigo/%s (N;) %s/%s (%s)" % (
    VERSION,
    DISTRO,
    RELEASE,
    CODENAME)

class RigoViewStates:
    # Possible Rigo Application UI States
    (
        BROWSER_VIEW_STATE,
        STATIC_VIEW_STATE,
        APPLICATION_VIEW_STATE,
        WORK_VIEW_STATE,
        CONFUPDATES_VIEW_STATE,
        NOTICEBOARD_VIEW_STATE,
        PREFERENCES_VIEW_STATE,
        REPOSITORY_VIEW_STATE,
        GROUPS_VIEW_STATE,
    ) = list(range(9))

class LocalActivityStates:
    (
        READY,
        UPDATING_REPOSITORIES,
        MANAGING_APPLICATIONS,
        UPGRADING_SYSTEM,
    ) = list(range(4))

    class BusyError(Exception):
        """
        Cannot acknowledge a Local Activity change.
        """

    class SameError(Exception):
        """
        Cannot set the same Local Activity.
        The proposed activity equals the current one.
        """

    class AlreadyReadyError(Exception):
        """
        Cannot acknowledge a Local Activity change to
        "READY" state, because we're already ready.
        """

    class UnbusyFromDifferentActivity(Exception):
        """
        Unbusy request from different activity.
        """
