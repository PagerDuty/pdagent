# Agent Installation Guide

## Introduction

The PagerDuty Agent is a helper program that you install on your monitoring
system to integrate your monitoring tools with PagerDuty.

The Agent includes command-line tools to accept events from your monitoring
tool to PagerDuty and a daemon process that handles the sending of these events
to PagerDuty. The daemon process takes care of buffering, retrying & throttling
of the sent events. The supported events are those listed in the
[PagerDuty Integration API](http://developer.pagerduty.com/documentation/integration/events).

The PagerDuty Agent is currently available in `deb` and `rpm` package formats
and tested on Ubuntu 10.04, Ubuntu 12.04 and CentOS 6.  For other platforms,
please [contact us](mailto:support@pagerduty.com)


## Prerequisites

The Agent supports sending events to PagerDuty Services of the “Generic API
system” type. If you do not have one set up, you can create one as follows:

1. In your account, under the Services tab, click “Add New Service”.
2. Enter a name for the service and select an escalation policy. Then, select
“Generic API system” for the Service Type.
2. Click the “Add Service” button.
3. Once the service is created, you’ll be taken to the service page. On this
page, you’ll see the “Service key”, which you will need when you send events
to PagerDuty via the Agent's command line tools.


## Agent Installation

### Ubuntu

1. Add the PagerDuty repository to your Ubuntu installation:

        sudo apt-get install python-software-properties
        sudo add-apt-repository ppa:pagerduty/tools

    ??? or: `sudo add-apt-repository "deb http://apt.pagerduty.com/tools lucid partner"` ?

    > Note: `python-software-properties` contains the command line tool
    > `add-apt-repository`.

2. Install the PagerDuty Agent package:

        sudo apt-get install pdagent

### CentOS

1. Add the PagerDuty repository to your CentOS installation:

        sudo yum-config-manager --add-repo http://rpm.pagerduty.com/tools.repo

    > or: `sudo add-apt-repository "deb http://apt.pagerduty.com/ lucid partner"` ?

2. Install the PagerDuty Agent package:

        sudo yum install pdagent

### Agent Daemon

If the install was successful, the Agent daemon process will be running.  You
can check this and start or stop it with the `service` command:

    sudo service pdagentd status

If the daemon is not running, check the logs at `/var/log/pdagent/pdagentd.log`.


## Sending an event to PagerDuty

To send an event to PagerDuty, you can use the `pd-send` command. This command
enqueues the event on the local disk and the Agent daemon will take care of
actually sending the event to the PagerDuty integation API. *This means that if
the `pdagentd` service is not running, the events will not be sent until the
service is started.*

Use the option `-h` or `--help` to check the usage:

```
~$ pd-send --help
usage: pd-send [-h] -k SERVICE_KEY -t {trigger,acknowledge,resolve}
               [-d DESCRIPTION] [-i INCIDENT_KEY] [-f FIELDS]

Queue up a trigger, acknowledge or resolve event to PagerDuty.

...
```

The `SERVICE_KEY` above is the "Service Key" that is shown on the service page
on the PagerDuty website.


## Integration with Monitoring Tools

You can integrate your shell scripts and monitoring tools with PagerDuty by having
them call the `pd-send` command with appropriate parameters.

However, the PagerDuty Agent also includes command-line tools for easier
integration with some specific monitoring tools.  See the following guides:

- Zabbix Integration Guide


