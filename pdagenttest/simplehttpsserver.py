import BaseHTTPServer
import ssl
from threading import Thread


class SimpleHTTPSServer(Thread):

    def __init__(self, cert_file_path, host="localhost", port=4443):
        Thread.__init__(self, name=self.__class__.__name__)
        self.cert_file_path = cert_file_path
        self.address = (host, port)
        self.httpd = BaseHTTPServer.HTTPServer(
            self.address,
            BaseHTTPServer.BaseHTTPRequestHandler
            )
        self.httpd.socket = ssl.wrap_socket(
            self.httpd.socket,
            certfile=self.cert_file_path,
            server_side=True
            )

    def run(self):
        self.httpd.serve_forever()

    def stop(self):
        self.httpd.shutdown()
        self.join()
