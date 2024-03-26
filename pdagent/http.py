#
# Ensures that HTTPS connections by PDAgent are made using a consistent
# SSLContext.
#
# PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
# --------------------------------------------
#
# 1. This LICENSE AGREEMENT is between the Python Software Foundation
# ("PSF"), and the Individual or Organization ("Licensee") accessing and
# otherwise using this software ("Python") in source or binary form and
# its associated documentation.
#
# 2. Subject to the terms and conditions of this License Agreement, PSF
# hereby grants Licensee a nonexclusive, royalty-free, world-wide
# license to reproduce, analyze, test, perform and/or display publicly,
# prepare derivative works, distribute, and otherwise use Python
# alone or in any derivative version, provided, however, that PSF's
# License Agreement and PSF's notice of copyright, i.e., "Copyright (c)
# 2001-2013 Python Software Foundation; All Rights Reserved" are retained in
# Python alone or in any derivative version prepared by Licensee.
#
# 3. In the event Licensee prepares a derivative work that is based on
# or incorporates Python or any part thereof, and wants to make
# the derivative work available to others as provided herein, then
# Licensee hereby agrees to include in any such work a brief summary of
# the changes made to Python.
#
# 4. PSF is making Python available to Licensee on an "AS IS"
# basis. PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
# IMPLIED. BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
# DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
# FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL NOT
# INFRINGE ANY THIRD PARTY RIGHTS.
#
# 5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
# FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
# A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON,
# OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.
#
# 6. This License Agreement will automatically terminate upon a material
# breach of its terms and conditions.
#
# 7. Nothing in this License Agreement shall be deemed to create any
# relationship of agency, partnership, or joint venture between PSF and
# Licensee. This License Agreement does not grant permission to use PSF
# trademarks or trade name in a trademark sense to endorse or promote
# products or services of Licensee, or any third party.
#
# 8. By copying, installing or otherwise using Python, Licensee
# agrees to be bound by the terms and conditions of this License
# Agreement.
#

import ssl

from pdagent.pdagentutil import find_in_sys_path
from pdagent.thirdparty.six.moves.http_client import HTTPSConnection
from pdagent.thirdparty.six.moves.urllib import request


try:
    # For Python > 3.6
    from ssl import PROTOCOL_TLS_CLIENT as ssl_client_protocol
except ImportError:
    # From Python > 2.7.9, < 3.6.
    from ssl import PROTOCOL_TLSv1_2 as ssl_client_protocol

# Custom HTTPS handler primarily for allowing us to pass a `source_address`
# through to `HTTPSConnection`
class CustomHTTPSHandler(request.HTTPSHandler):
    def __init__(self, **kwargs):
        self.source_address = kwargs.pop("source_address", '0.0.0.0')
        request.HTTPSHandler.__init__(self, **kwargs)

    # Overrides `HTTPSHandler.https_open`.
    def https_open(self, req):
        return self.do_open(self._connection, req)

    def _connection(self, host, **kwargs):
        kwargs["source_address"] = self.source_address
        return HTTPSConnection(host, **kwargs)


def urlopen(url, **kwargs):
    source_address = kwargs.pop("source_address", '0.0.0.0')

    opener = request.build_opener(CustomHTTPSHandler(
            context=_create_ssl_context(),
            source_address=(source_address, 0)
        ))

    return opener.open(url, **kwargs)

def _create_ssl_context():
    # Some of this configuration is redundant for PROTOCOL_TLS_CLIENT, but
    # repeating for the benefit of legacy protocols.
    context = ssl.SSLContext(ssl_client_protocol)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_default_certs()
    return context

