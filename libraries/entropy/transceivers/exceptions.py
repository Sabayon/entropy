# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy base transceivers exception module}.

"""
from entropy.exceptions import EntropyException

class TransceiverError(EntropyException):
    """Generic entropy.transceivers error"""

class UriHandlerNotFound(TransceiverError):
    """
    Raised when URI handler (in entropy.transceivers.EntropyTransceiver)
    for given URI is not available.
    """

class TransceiverConnectionError(TransceiverError):
    """ Connection error on transceiver """
