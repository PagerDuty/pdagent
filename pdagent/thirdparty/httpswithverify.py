#
# Verified HTTPS connection - based on httplib & urllib2.
# See http://docs.python.org/2/license.html for license.
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
        self.sock = ssl.wrap_socket(sock,
                                    keyfile=self.key_file,
                                    certfile=self.cert_file,
                                    cert_reqs=ssl.CERT_REQUIRED,
                                    ca_certs=self.ca_certs)
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
