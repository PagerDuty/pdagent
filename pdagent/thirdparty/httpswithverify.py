#
# Verified HTTPS connection.
#
# Based on Python 2.7's httplib & urllib2.
#
# Source: http://www.python.org/
#
# Modifications by PagerDuty:
#  - VerifyingHTTPSConnection wraps httplib.HTTPSConnection adding
#       validation of server SSL cert using given CA certs.
#  - VerifyingHTTPSHandler uses VerifyingHTTPSConnection
#  - urlopen that uses VerifyingHTTPSHandler
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


import httplib
import urllib2
import socket

from pdagent.pdagentutil import find_in_sys_path
from pdagent.thirdparty.ssl_match_hostname import \
    match_hostname, CertificateError

if not hasattr(httplib, 'HTTPS'):
    raise SystemExit(
        "httplib does not support https!\n"
        "Please ensure that you have Python version 2.6 or higher,\n"
        "and have ssl module installed. (See https://pypi.python.org/pypi/ssl/)"
        )

try:
    import ssl
except ImportError:
    raise SystemExit(
        "The 'ssl' module is not installed!\n" +
        "See https://pypi.python.org/pypi/ssl/ for installation instructions."
        )

DEFAULT_CA_CERTS_FILE = find_in_sys_path("pdagent/root_certs/ca_certs.pem")

class VerifyingHTTPSConnection(httplib.HTTPSConnection):
    """This class allows communication via SSL after verifying the
    server's certificate."""
    # this class is a modified version of httplib.HTTPSConnection

    def __init__(self, host, **kwargs):
        self.ca_certs = kwargs.pop("ca_certs", None)
        httplib.HTTPSConnection.__init__(self, host, **kwargs)

    def connect(self):
        """Connects to a host on a given (SSL) port, using a
        certificate-verifying socket wrapper."""

        args = [(self.host, self.port), self.timeout]
        if hasattr(self, 'source_address'):
            args.append(self.source_address)
        sock = socket.create_connection(*args)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()

        # require server certificate to be provided, and pass along
        # the ca_certs file.
        self.sock = ssl.wrap_socket(
            sock,
            keyfile=self.key_file,
            certfile=self.cert_file,
            cert_reqs=ssl.CERT_REQUIRED,
            ca_certs=self.ca_certs
            )
        try:
            match_hostname(self.sock.getpeercert(), self.host)
        except CertificateError:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
            raise

class VerifyingHTTPSHandler(urllib2.HTTPSHandler):
    """This handler uses HTTPS connections that verify the server's
    SSL certificate."""
    # this class is a modified version of urllib2.HTTPSHandler

    def __init__(self, **kwargs):
        self.ca_certs = kwargs.pop("ca_certs", None)
        urllib2.HTTPSHandler.__init__(self, **kwargs)

    def https_open(self, req):
        return self.do_open(self._proxyHTTPSConnection, req)

    def _proxyHTTPSConnection(self, host, **kwargs):
        new_kwargs = {
            "ca_certs": self.ca_certs
            }
        new_kwargs.update(kwargs)  # allows overriding ca_certs
        return VerifyingHTTPSConnection(host, **new_kwargs)

url_opener_cache = dict()

def urlopen(url, **kwargs):
    ca_certs = kwargs.pop("ca_certs", DEFAULT_CA_CERTS_FILE)
    if ca_certs not in url_opener_cache:
        # create and cache an opener; not thread-safe, but doesn't matter.
        url_opener_cache[ca_certs] = \
            urllib2.build_opener(VerifyingHTTPSHandler(ca_certs=ca_certs))
    return url_opener_cache[ca_certs].open(url, **kwargs)
