class MockUrlLib:

    def __init__(self):
        self.request = None
        self.response = None

    def urlopen(self, request, **kwargs):
        self.request = request
        return self.response

