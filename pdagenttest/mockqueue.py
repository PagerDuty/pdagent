class MockQueue:

    def __init__(
            self,
            event=None,
            status=None,
            aggregated=None,
            throttle_info=None,
            cleanup_age_secs=None
            ):
        self.event = event
        self.status = status
        self.expected_aggregated = aggregated
        self.expected_throttle_info = throttle_info
        self.expected_cleanup_age = cleanup_age_secs
        self.consume_code = None
        self.cleaned_up = False

    def get_status(self, aggregated=False, throttle_info=False):
        if aggregated == self.expected_aggregated and \
                throttle_info == self.expected_throttle_info:
            return self.status
        raise Exception(
            (
            "Received aggregated=%s and throttle_info=%s; " +
            "expected aggregated=%s and throttle_info=%s"
            ) %
            (
            aggregated, throttle_info,
            self.expected_aggregated, self.expected_throttle_info
            )
            )

    def flush(self, consume_func, stop_check_func):
        self.consume_code = consume_func(self.event, self.event)

    def cleanup(self, before):
        if before == self.expected_cleanup_age:
            self.cleaned_up = True
        else:
            raise Exception(
                "Received cleanup_before=%s, expected=%s" %
                (before, self.expected_cleanup_age)
                )
