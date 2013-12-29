# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client QA Interface}.

"""
from entropy.qa import ErrorReport
from entropy.client.interfaces import Client
from entropy.core.settings.base import SystemSettings
from entropy.const import etpConst
from entropy.exceptions import PermissionDenied
from entropy.services.client import WebService

class UGCErrorReport(ErrorReport):

    """
    Entropy Errors Reporting Interface that works over User Generated
    Content (UGC) infrastructure. This version is bound to a specific
    repository which MUST provide UGC services, otherwise, the error
    submission will fail.

    This class will allow Entropy repository maintainers to know about
    critical errors happened during normal operation.
    Here is an example on how to use this:

        error_interface = UGCErrorReport('sabayonlinux.org')
        error_interface.prepare()
        reported = error_interface.submit()
        if reported:
            print("error reported succesfully")
        else:
            print("cannot report error")
    """

    def __init__(self, repository_id):
        """
        object constructor, repository_id must be a valid repository
        identifier.

        @param repository_id: valid repository identifier
        @type repository_id: string
        """
        super(UGCErrorReport, self).__init__("#fake#")

        self.__system_settings = SystemSettings()
        self._entropy = Client()
        if repository_id not in self.__system_settings['repositories']['order']:
            raise AttributeError('invalid repository_id provided')
        self.__repository_id = repository_id

        self._factory = self._entropy.WebServices()
        try:
            self._webserv = self._factory.new(self.__repository_id)
        except WebService.UnsupportedService:
            raise AttributeError('Web Services not supported by %s' % (
                self.__repository_id,))

        try:
            available = self._webserv.service_available()
        except WebService.WebServiceException:
            available = False

        if not available:
            raise AttributeError('Web Services not supported by %s (2)' % (
                self.__repository_id,))

    def submit(self):
        """
        Overridden method from ErrorReport.
        Does the actual error submission. You must call it after prepare().

        @return submission status -- bool
        """
        if not self.generated:
            raise PermissionDenied("Not prepared yet")

        try:
            self._webserv.report_error(self.params)
        except WebService.WebServiceException:
            return False
        return True
