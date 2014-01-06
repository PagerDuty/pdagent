#
# Verified HTTPS connection - based on httplib & urllib2.
# See http://docs.python.org/2/license.html for license.
#

import httplib
import urllib2
import socket

_verified_https_possible = False

from pdagent.pdagentutil import find_in_sys_path
DEFAULT_CA_CERTS_FILE = find_in_sys_path("pdagent/root_certs/ca_certs.pem")

# TODO test for Python <2.6
if hasattr(httplib, 'HTTPS'):

    try:
        import ssl
    except ImportError:
        pass
    else:
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

                from pdagent.backports.ssl_match_hostname import \
                    match_hostname, CertificateError

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

        _verified_https_possible = True


def urlopen(url, **kwargs):
    ca_certs = kwargs.pop("ca_certs", DEFAULT_CA_CERTS_FILE)
    if _verified_https_possible:
        # TODO cache the opener?
        opener = urllib2.build_opener(VerifyingHTTPSHandler(ca_certs=ca_certs))
        return opener.open(url, **kwargs)
    else:
        return urllib2.urlopen(url, **kwargs)
