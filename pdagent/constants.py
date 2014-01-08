# PDQueue event consumption function return codes.
EVENT_CONSUMED = 0
EVENT_BAD_ENTRY = 1
EVENT_NOT_CONSUMED = 2
EVENT_STOP_ALL = 3
EVENT_BACKOFF_SVCKEY_BAD_ENTRY = 4
EVENT_BACKOFF_SVCKEY_NOT_CONSUMED = 5

# PD event integration API.
EVENTS_API_BASE = \
    "https://events.pagerduty.com/generic/2010-04-15/create_event.json"
