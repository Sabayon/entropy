# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client QA Interface}.

"""
from entropy.qa import ErrorReportInterface
from entropy.client.interfaces import Client
from entropy.core.settings.base import SystemSettings
from entropy.const import etpConst
from entropy.exceptions import IncorrectParameter, OnlineMirrorError, \
    PermissionDenied
from entropy.i18n import _

class UGCErrorReportInterface(ErrorReportInterface):

    """
    Entropy Errors Reporting Interface that works over User Generated
    Content (UGC) infrastructure. This version is bound to a specific
    repository which MUST provide UGC services, otherwise, the error
    submission will fail.

    This class will allow Entropy repository maintainers to know about
    critical errors happened during normal operation.
    Here is an example on how to use this:

        error_interface = UGCErrorReportInterface('sabayonlinux.org')
        error_interface.prepare()
        reported = error_interface.submit()
        if reported:
            print("error reported succesfully")
        else:
            print("cannot report error")
    """

    def __init__(self, repository_id = None):
        """
        object constructor, repository_id must be a valid repository
        identifier.

        @param repository_id -- valid repository identifier
        @type basestring
        """
        ErrorReportInterface.__init__(self, '#fake#')
        self.__system_settings = SystemSettings()

        if repository_id == None:
            repository_id = etpConst['officialrepositoryid']

        self.entropy = Client()
        self.__repository_id = repository_id
        if self.entropy.UGC == None:
            # enable UGC
            from entropy.client.services.ugc.interfaces import Client as ugc
            self.entropy.UGC = ugc(self.entropy)

        if repository_id not in self.__system_settings['repositories']['order']:
            raise IncorrectParameter('invalid repository_id provided')
        if not self.entropy.UGC.is_repository_eapi3_aware(repository_id):
            raise OnlineMirrorError('UGC not supported by the provided repo')

    def submit(self):
        """
        Overloaded method from ErrorReportInterface.
        Does the actual error submission. You must call it after prepare().

        @return submission status -- bool
        """

        if self.generated:
            done, err_msg = self.entropy.UGC.report_error(self.__repository_id,
                self.params)
            if done:
                return True
            return False
        else:
            mytxt = _("Not prepared yet")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))
