# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Services Exceptions module}.
    These are the exceptions raised by Entropy Services RPC system.

"""
from entropy.exceptions import EntropyException

class EntropyServicesError(EntropyException):
    """ Generic Entropy Services exception. All classes here belong to this. """

class TransmissionError(EntropyServicesError):
    """ Generic transmission error exception """

class BrokenPipe(TransmissionError):
    """ Broken pipe transmission error """

class SSLTransmissionError(TransmissionError):
    """ Error on SSL socket """

class ServiceConnectionError(EntropyServicesError):
    """Cannot connect to service"""

class TimeoutError(EntropyServicesError):
    """ Timeout error """
