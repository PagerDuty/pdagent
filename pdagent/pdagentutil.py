#
# Python utility module for sending events to PagerDuty Integration API.
#
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Uses the PagerDuty Integration API:
# http://developer.pagerduty.com/documentation/integration/events
#

import json
import os


def find_in_sys_path(file_path):
    import os
    import sys
    for directory in sys.path:
        abs_path = os.path.join(directory, file_path)
        if os.access(abs_path, os.R_OK):
            return abs_path
    return None

def ensure_readable_directory(dir):
    if not os.access(dir, os.R_OK):
        raise Exception(
            "Can't read directory %s, please check permissions" % dir
        )

def ensure_writable_directory(dir):
    if not os.access(dir, os.W_OK):
        raise Exception(
            "Can't write to directory %s, please check permissions" % dir
        )


def queue_event(
        queue,
        event_type, service_key, incident_key, description, details
        ):
    if not incident_key and event_type is "trigger":
        import uuid
        incident_key = "pdagent-%s" % str(uuid.uuid4())
    event = _build_event_json_str(
        event_type, service_key, incident_key, description, details
        )
    queue.enqueue(service_key, event)


def resurrect_events(queue, service_key):
    queue.resurrect(service_key)


def get_status(queue, service_key):
    return queue.get_status(service_key)

def _build_event_json_str(
    event_type, service_key, incident_key, description, details
    ):
    d = {
        "service_key": service_key,
        "event_type": event_type,
        "details": details,
    }
    if incident_key is not None:
        d["incident_key"] = incident_key
    if description is not None:
        d["description"] = description

    return json.dumps(
        d,
        separators=(',', ':'),  # compact json str
        sort_keys=True
    )
