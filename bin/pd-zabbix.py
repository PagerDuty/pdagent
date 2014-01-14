#!/usr/bin/python
#
# Python script to send incidents from Zabbix to PagerDuty.
#
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#

# Parse the Zabbix message body. The body MUST be in this format:
#
# name:{TRIGGER.NAME}
# id:{TRIGGER.ID}
# status:{TRIGGER.STATUS}
# hostname:{HOSTNAME}
# ip:{IPADDRESS}
# value:{TRIGGER.VALUE}
# event_id:{EVENT.ID}
# severity:{TRIGGER.SEVERITY}
#
def _parse_zabbix_body(body_str):
    return dict(line.strip().split(':', 1) for line in body_str.strip().split('\n'))

# Parse the Zabbix message subject.
# The subject MUST be one of the following:
#
# trigger
# resolve
#
def _parse_zabbix_subject(subject_str):
    return subject_str

def main():
    from pdagent.pdagentutil import queue_event
    agent_config = pdagent.config.load_agent_config()

    # The first argument is the service key
    service_key = sys.argv[1]

    # The second argument is the message type
    message_type = _parse_zabbix_subject(sys.argv[2])

    # The third argument is the data
    details = _parse_zabbix_body(sys.argv[3])

    # Incident key is created by concatenating trigger id and host name.
    # Remember, incident key is used for de-duping and also to match trigger with resolve messages
    incident_key = "%s-%s" % (details["id"], details["hostname"])

    # The description that is rendered in PagerDuty and also sent as SMS and phone alert
    description = "%s : %s for %s" % (details["name"], details["status"], details["hostname"])

    queue_event(
        agent_config.get_outqueue_dir(),
        message_type, service_key, incident_key, description, details
        )

if __name__ == "__main__":
    try:
        import pdagent.config
    except ImportError:
        # Fix up for dev layout
        import sys
        from os.path import realpath, dirname
        sys.path.append(dirname(dirname(realpath(__file__))))
        import pdagent.config
    main()
