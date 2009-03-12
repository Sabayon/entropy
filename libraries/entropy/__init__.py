# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

# Old critical imports kept for compatibility
# WARNING WARNING WARNING WARNING WARNING WARNING WARNING
# !!! Will be removed soon !!!
# WARNING WARNING WARNING WARNING WARNING WARNING WARNING
# from entropy.client.interfaces import Client as EquoInterface, Package as PackageInterface, Repository as RepoInterface
# from entropy.db import LocalRepository as EntropyDatabaseInterface, dbapi2
# from entropy.spm import Spm as SpmInterface
# from entropy.client.misc import FileUpdates
# from entropy.services.interfaces import SocketHost as SocketHostInterface
# from entropy.services.skel import SocketCommands as SocketCommandsSkel, \
#    SocketAuthenticator as SocketAuthenticatorSkel, RemoteDatabase as RemoteDbSkelInterface, \
#    Authenticator as DistributionAuthInterface
# from entropy.server.interfaces import Server as ServerInterface, MirrorsServer as ServerMirrorsInterface
# from entropy.services.ugc.interfaces import Server as DistributionUGCInterface, Client as SystemSocketClientInterface
# from entropy.client.services.ugc.interfaces import Client as UGCClientInterface, AuthStore as UGCClientAuthStore, Cache as UGCCacheInterface
# from entropy.client.services.ugc.commands import Base as EntropySocketClientCommands, Client as RepositorySocketClientCommands
# from entropy.client.services.system.commands import Client as SystemManagerClientCommands, Repository as SystemManagerRepositoryClientCommands
# from entropy.client.services.system.interfaces import Client as SystemManagerClientInterface
# from entropy.client.services.system.methods import Base as SystemManagerMethodsInterface, Repository as SystemManagerRepositoryMethodsInterface
# from entropy.services.ugc.commands import UGC as DistributionUGCCommands
# from entropy.services.auth_interfaces import phpBB3Auth as phpBB3AuthInterface
# from entropy.services.authenticators import phpBB3 as phpbb3Authenticator
# from entropy.services.commands import phpBB3 as phpbb3Commands
# from entropy.services.repository.interfaces import Server as RepositorySocketServerInterface
# from entropy.services.system.commands import Repository as SystemManagerRepositoryCommands
# from entropy.services.system.interfaces import TaskExecutor as SystemManagerExecutorInterface, Server as SystemManagerServerInterface
# from entropy.services.system.executors import Base as SystemManagerExecutorServerRepositoryInterface
