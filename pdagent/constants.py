from pdagent import enum


# Agent version.
AGENT_VERSION = "1.0"

# PDQueue event consumption function return codes.
ConsumeEvent = enum(
    'CONSUMED',
    'BAD_ENTRY',
    'NOT_CONSUMED',
    'STOP_ALL',
    'BACKOFF_SVCKEY_BAD_ENTRY',
    'BACKOFF_SVCKEY_NOT_CONSUMED',
)

# PD event integration API.
EVENTS_API_BASE = \
    "https://events.pagerduty.com/generic/2010-04-15/create_event.json"

# TODO PD phone-home end-point.
PHONE_HOME_URI = "http://localhost:4567/phonehome"
