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

class LoadersMixin:

    def __init__(self):
        self._spm_cache = {}

        from entropy.client.interfaces.trigger import Trigger
        from entropy.client.interfaces.repository import Repository
        from entropy.client.interfaces.package import Package
        from entropy.security import Repository as RepositorySecurity
        from entropy.client.interfaces.sets import Sets
        self.__PackageLoader = Package
        self.__RepositoryLoader = Repository
        self.__TriggerLoader = Trigger
        self.__RepositorySecurityLoader = RepositorySecurity
        self.__SetsLoader = Sets

    def Sets(self):
        """
        Load Package Sets interface
        """
        return self.__SetsLoader(self)

    def Security(self):
        """
        Load Entropy Security Advisories interface
        """
        return System(self)

    def RepositorySecurity(self, keystore_dir = None):
        """
        @raise RepositorySecurity.GPGError: GPGError based instances in case
            of problems.
        """
        if keystore_dir is None:
            keystore_dir = etpConst['etpclientgpgdir']
        return self.__RepositorySecurityLoader(
            keystore_dir = keystore_dir)

    def QA(self):
        """
        Load Entropy QA interface
        """
        qa_intf = QAInterface()
        qa_intf.output = self.output
        qa_intf.ask_question = self.ask_question
        qa_intf.input_box = self.input_box
        qa_intf.set_title = self.set_title
        return qa_intf

    def Triggers(self, *args, **kwargs):
        return self.__TriggerLoader(self, *args, **kwargs)

    def Repositories(self, *args, **kwargs):
        cl_id = self.sys_settings_client_plugin_id
        client_data = self._settings[cl_id]['misc']
        kwargs['gpg'] = client_data['gpg']
        return self.__RepositoryLoader(self, *args, **kwargs)

    def Spm(self):
        myroot = etpConst['systemroot']
        cached = self._spm_cache.get(myroot)
        if cached is not None:
            return cached
        spm = get_spm(self)
        self._spm_cache[myroot] = spm
        return spm

    def Spm_class(self):
        """
        Return Source Package Manager default plugin class.
        """
        return get_spm_default_class()

    def Package(self):
        return self.__PackageLoader(self)

    def Settings(self):
        """
        Return SystemSettings instance
        """
        return self._settings

    def Cacher(self):
        """
        Return EntropyCacher instance
        """
        return self._cacher

