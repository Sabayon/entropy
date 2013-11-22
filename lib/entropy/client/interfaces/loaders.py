# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Instance Loaders Interface}.

"""
from entropy.spm.plugins.factory import get_default_instance as get_spm, \
    get_default_class as get_spm_default_class

from entropy.const import etpConst
from entropy.qa import QAInterface
from entropy.security import System
from entropy.security import Repository as RepositorySecurity

class LoadersMixin:

    def __init__(self):
        self._spm_cache = {}
        # instantiate here to avoid runtime loading, that can cause failures
        # during complete system upgrades
        from entropy.client.interfaces.trigger import Trigger
        from entropy.client.interfaces.repository import Repository
        from entropy.client.interfaces.package import Package
        from entropy.client.interfaces.sets import Sets
        from entropy.client.misc import ConfigurationUpdates
        from entropy.client.services.interfaces import \
            ClientWebServiceFactory, RepositoryWebServiceFactory
        self.__package_loader = Package
        self.__repository_loader = Repository
        self.__trigger_loader = Trigger
        self.__sets_loader = Sets
        self.__configuration_updates_loader = ConfigurationUpdates
        self.__webservice_factory = ClientWebServiceFactory
        self.__repo_webservice_factory = RepositoryWebServiceFactory

    def Sets(self):
        """
        Load Package Sets interface object

        @return: Sets instance object
        @rtype: entropy.client.interfaces.sets.Sets
        """
        return self.__sets_loader(self)

    def Security(self):
        """
        Load Entropy Security Advisories interface object

        @return: Repository Security instance object
        @rtype: entropy.security.System
        """
        return System(self)

    def RepositorySecurity(self, keystore_dir = None):
        """
        Load Entropy Repository Security interface object

        @return: Repository Repository Security instance object
        @rtype: entropy.security.Repository
        @raise RepositorySecurity.GPGError: GPGError based instances in case
            of problems.
        """
        if keystore_dir is None:
            keystore_dir = etpConst['etpclientgpgdir']
        return RepositorySecurity(keystore_dir = keystore_dir)

    def QA(self):
        """
        Load Entropy QA interface object

        @rtype: entropy.qa.QAInterface
        """
        qa_intf = QAInterface()
        qa_intf.output = self.output
        qa_intf.ask_question = self.ask_question
        qa_intf.input_box = self.input_box
        qa_intf.set_title = self.set_title
        return qa_intf

    def Triggers(self, *args, **kwargs):
        return self.__trigger_loader(self, *args, **kwargs)

    def Repositories(self, *args, **kwargs):
        """
        Load Entropy Repositories manager instance object

        @return: Repository instance object
        @rtype: entropy.client.interfaces.repository.Repository
        """
        cl_id = self.sys_settings_client_plugin_id
        client_data = self._settings[cl_id]['misc']
        kwargs['gpg'] = client_data['gpg']
        return self.__repository_loader(self, *args, **kwargs)

    def WebServices(self):
        """
        Load the Entropy Web Services Factory interface, that can be used
        to obtain a WebService object that is able to communicate with
        repository remote services, if available.

        @return: WebServicesFactory instance object
        @rtype: entropy.client.services.interfaces.WebServicesFactory
        """
        return self.__webservice_factory(self)

    def RepositoryWebServices(self):
        """
        Load the Repository Entropy Web Services Factory interface, that can
        be used to obtain a RepositoryWebService object that is able to
        communicate with repository remote services, querying for package
        metadata and general repository status.

        @return: RepositoryWebServiceFactory instance object
        @rtype: entropy.client.services.interfaces.RepositoryWebServiceFactory
        """
        return self.__repo_webservice_factory(self)

    def Spm(self):
        """
        Load Source Package Manager instance object
        """
        myroot = etpConst['systemroot']
        cached = self._spm_cache.get(myroot)
        if cached is not None:
            return cached
        spm = get_spm(self)
        self._spm_cache[myroot] = spm
        return spm

    def Spm_class(self):
        """
        Load Source Package Manager default plugin class
        """
        return get_spm_default_class()

    def Package(self):
        """
        Load Entropy Package instance object

        @return:
        @rtype: entropy.client.interfaces.package.Package
        """
        return self.__package_loader(self)

        """
        """

    def ConfigurationUpdates(self):
        """
        Return Entropy Configuration File Updates management object.
        """
        return self.__configuration_updates_loader(self)

    def Settings(self):
        """
        Return SystemSettings instance object
        """
        return self._settings

    def ClientSettings(self):
        """
        Return SystemSettings Entropy Client plugin metadata dictionary
        """
        return self._settings[self.sys_settings_client_plugin_id]

    def Cacher(self):
        """
        Return EntropyCacher instance object

        @return: EntropyCacher instance object
        @rtype: entropy.cache.EntropyCacher
        """
        return self._cacher
