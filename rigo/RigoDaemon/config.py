# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-3

    B{Entropy Package Manager Rigo Daemon Config}.

"""

class DbusConfig:

    BUS_NAME = "org.sabayon.Rigo"
    OBJECT_PATH = "/"

class PolicyActions:

    # PolicyKit update action
    UPDATE_REPOSITORIES = "org.sabayon.RigoDaemon.update"
    UPGRADE_SYSTEM = "org.sabayon.RigoDaemon.upgrade"
    MANAGE_APPLICATIONS = "org.sabayon.RigoDaemon.manage"
    MANAGE_CONFIGURATION = "org.sabayon.RigoDaemon.configuration"
