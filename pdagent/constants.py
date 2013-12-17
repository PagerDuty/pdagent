# PDQueue event consumption function return codes.
EVENT_CONSUMED = 0
EVENT_NOT_CONSUMED = 1
EVENT_CONSUME_ERROR = 2

# PD event integration API.
EVENTS_API_BASE = \
    "https://events.pagerduty.com/generic/2010-04-15/create_event.json"
