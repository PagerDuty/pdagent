class MockResponse:

    def __init__(self, code=200, data=None):
        self.code = code
        self.data = data

    def getcode(self):
        return self.code

    def read(self):
        return self.data

