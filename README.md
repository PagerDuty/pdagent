# Introduction

The PagerDuty Agent is a program that lets you easily integrate your monitoring
system with PagerDuty.

It includes command-line tools to trigger, acknowledge & resolve PagerDuty
incidents.

The supported events are those listed in the PagerDuty Integration API:

> <http://developer.pagerduty.com/documentation/integration/events>

The PagerDuty Agent is completely open-source which means that you can download
the source code and customize it for your needs.


## Developing

The Agent requires Python 2.6 or 2.7. The instructions here assume that you're
on a Mac.

You can start your development copy of the Agent daemon with the command:

    bin/pdagentd.py

In development the daemon automatically creates a `tmp` directory where it
stores its various work files. The daemon's pid is stored in the file
`tmp/pdagentd.pid`, so you can stop the daemon with the following command:

    kill `cat tmp/pdagentd.pid`

Similarly, you can use the `pd-send` command immediately.

```
~/w/pdagent$ bin/pd-send -h
usage: pd-send [-h] -k SERVICE_KEY -t {trigger,acknowledge,resolve}
               [-d DESCRIPTION] [-i INCIDENT_KEY] [-f FIELDS]

Queue up a trigger, acknowledge, or resolve event to PagerDuty.
...
```

Make sure that you have run the daemon at least once so that the `tmp`
directory exists.

For IDE setup instructions see `pydev-setup.txt` or `idea-setup.txt`. Apart
from the usual benefits, the IDEs provide PEP-8 warnings which we care about.


### Build Tools

To perform a complete automated build, you'll need to install Scons and Vagrant
(along with VirtualBox - other combinations not tested).

See the files `scons-setup.txt` and `vagrant-setup.txt` for setup instructions.


### Running Unit Tests

You can run the unit tests with the following command:

    scons test-local

To run them without installing SCons, use the `run-tests.py` test runner, e.g.:

    python run-tests.py pdagenttest/test_*.py pdagenttest/thirdparty/test_*.py


### Building Packages

To perform a full automated clean build of the Agent, perform the following
steps:

1. Configure signing certificates by following the _One-time Setup_
instructions in `build-linux/howto.txt`.

2. Run the following commands:

        scons -clean
        scons local-repo

    Note that this will spin up multiple virtual machines using Vagrant to run
    tests and perform builds on.

3. Run integration tests on the packages with the command:

        scons test-integration

If you want to build packages by hand, follow the instructions in
`build-linux/howto.txt`.

Similarly, you can check the SCons targets using `scons -h` for instructions on
performing specific builds tasks and on specific VMs.
