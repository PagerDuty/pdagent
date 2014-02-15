import unittest

import socket
from ssl import SSLError
import time
from urllib2 import URLError
from pdagent.thirdparty.httpswithverify import urlopen
from pdagent.thirdparty.ssl_match_hostname import CertificateError
from pdagenttest.simplehttpsserver import SimpleHTTPSServer


def _make_url(host, protocol="https", port=None):
    if port:
        return "%s://%s:%s/" % (protocol, host, port)
    return "%s://%s/" % (protocol, host)


# the external server we test with.
_SERVER = "www.google.com"
# Response code for successful connections.
_SUCCESS_RESPONSE_CODE = 200


class PDVerifiedHttpsTest(unittest.TestCase):

    def test_valid_cert(self):
        # Connect to server with a valid cert signed by a CA.
        res = urlopen(_make_url(_SERVER))
        self.assertEqual(res.getcode(), _SUCCESS_RESPONSE_CODE)

    def test_cert_with_different_domain(self):
        # connect using IP address instead of name in cert; this should fail
        # cert domain validation.
        url_cert_wrong_domain = _make_url(socket.gethostbyname(_SERVER))
        self.assertRaises(CertificateError, urlopen, url_cert_wrong_domain)

    def test_self_signed_cert(self):
        # start and connect to a local https server using a self-signed cert.
        local_server = None
        try:
            from os.path import dirname, join, realpath
            host = 'localhost'
            port = 4443
            cert_file_path = join(
                dirname(dirname(realpath(__file__))),
                'self_signed.pem'
                )
            local_server = SimpleHTTPSServer(
                cert_file_path=cert_file_path,
                host=host,
                port=port
                )
            local_server.start()
            try:
                urlopen(_make_url(host, port=port))
            except URLError as e:
                if e.reason and type(e.reason) is SSLError:
                    # this is the right error.
                    pass
                else:
                    raise
            else:
                # we don't expect zero errors.
                self.fail("Didn't encounter expected error")
        finally:
            if local_server:
                local_server.stop()

    def test_no_https(self):
        # try http; should complete without any certificate-related error.
        res = urlopen(_make_url(_SERVER, protocol="http"))
        self.assertEqual(res.getcode(), _SUCCESS_RESPONSE_CODE)

if __name__ == '__main__':
    unittest.main()
