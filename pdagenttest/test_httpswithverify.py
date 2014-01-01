import unittest

from pdagent.backports.ssl_match_hostname import CertificateError
from pdagent.httpswithverify import urlopen
from urllib2 import HTTPError, URLError
from ssl import SSLError


class PDVerifiedHttpsTest(unittest.TestCase):

    def test_valid_cert(self):
        try:
            urlopen('https://caduceus.pd-internal.com/')
        except HTTPError as e:
            # if the server cert is valid, we connected to the server,
            # and server has complained to us about authorization.
            self.assertEqual(e.getcode(), 401)
        else:
            # we don't expect zero errors.
            self.fail("Didn't encounter expected error")

    def test_cert_with_different_domain(self):
        # we should get a CertificateError here because this url uses a
        # certificate issued to cloudfront.net
        self.assertRaises(
            CertificateError, urlopen, 'https://www.cloudoverflow.com/')

    def test_self_signed_cert(self):
        try:
            urlopen('https://events.pd-staging.com/')
        except URLError as e:
            if e.reason and type(e.reason) is SSLError:
                # this is the right error.
                pass
            else:
                raise
        else:
            # we don't expect zero errors.
            self.fail("Didn't encounter expected error")

    def test_no_https(self):
        # try http; should complete without any certificate-related error.
        try:
            urlopen('http://www.cloudoverflow.com/')
        except HTTPError as e:
            # if the server cert is not checked, we will connect,
            # and will be denied access by the server.
            self.assertEqual(e.getcode(), 403)
        else:
            # we don't expect zero errors.
            self.fail("Didn't encounter expected error")

if __name__ == '__main__':
    unittest.main()
