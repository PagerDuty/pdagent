# PDQueue event consumption function return codes.
EVENT_CONSUMED = 0
EVENT_BAD_ENTRY = 1
EVENT_BACKOFF_SVCKEY = 2
EVENT_STOP_ALL = 4
EVENT_NOT_CONSUMED = 8

# PD event integration API.
EVENTS_API_BASE = \
    "https://events.pagerduty.com/generic/2010-04-15/create_event.json"
