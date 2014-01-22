import unittest

from pdagent.backports.ssl_match_hostname import CertificateError
from pdagent.thirdparty.httpswithverify import urlopen
from urllib2 import HTTPError, URLError
from ssl import SSLError


# FIXME: before open-sourcing, we may want to stop
# pointing these to PD servers!

# Server with a valid cert signed by a CA
_URL_VALID_CERT = 'https://caduceus.pd-staging.com/'
_URL_VALID_CERT_RESPONSE_CODE = 401

# Server with a valid cert but domain does not match
# cloudfront.com uses cert issued to cloudfront.net
_URL_CERT_WRONG_DOMAIN = 'https://www.cloudoverflow.com/'

# Server with a self-signed cert
_URL_SELF_SIGNED_CERT = 'https://events.pd-staging.com/'

# Plain HTTP server
_URL_HTTP = 'http://www.cloudoverflow.com/'
_URL_HTTP_RESPONSE_CODE = 403


class PDVerifiedHttpsTest(unittest.TestCase):

    def test_valid_cert(self):
        try:
            urlopen(_URL_VALID_CERT)
        except HTTPError as e:
            # if the server cert is valid, we connected to the server
            self.assertEqual(e.getcode(), _URL_VALID_CERT_RESPONSE_CODE)
        else:
            # we don't expect zero errors.
            self.fail("Didn't encounter expected error")

    def test_cert_with_different_domain(self):
        self.assertRaises(CertificateError, urlopen, _URL_CERT_WRONG_DOMAIN)

    def test_self_signed_cert(self):
        try:
            urlopen(_URL_SELF_SIGNED_CERT)
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
            urlopen(_URL_HTTP)
        except HTTPError as e:
            # if the server cert is not checked, we will connect
            self.assertEqual(e.getcode(), _URL_HTTP_RESPONSE_CODE)
        else:
            # we don't expect zero errors.
            self.fail("Didn't encounter expected error")

if __name__ == '__main__':
    unittest.main()
