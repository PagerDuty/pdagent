> This is the source code and project. For the PagerDuty Agent Install Guide,
> see http://www.pagerduty.com/docs/guides/agent-install-guide/

# Introduction

The PagerDuty Agent is a program that lets you easily integrate your monitoring
system with PagerDuty.

It includes command-line tools to trigger, acknowledge & resolve PagerDuty
incidents.

The supported events are those listed in the PagerDuty Integration API:

> <http://developer.pagerduty.com/documentation/integration/events>

The PagerDuty Agent is completely open-source which means that you can download
the source code and customize it for your needs.

The Agent requires Python 2.6 or 2.7. The instructions here assume that you're
on a Mac.

## About this version

This version of the PagerDuty Agent supports both V1
(https://v2.developer.pagerduty.com/docs/events-api) and V2
(https://v2.developer.pagerduty.com/docs/events-api-v2) Event APIs. If a version
is not explicitly stated with the -api argument, it will default to V1, and
should perform identically to the previous version. The V2 Api supports a richer
set of parameters that may be useful.

In the background it determines the API endpoint by the checking if the
generated message contains "service_key" (V1) or "routing_key"
(V2) - in a simple textual manner (by the time it is on the queue it is a string
containing JSON and not a tree structure)


## Developing

### Running in Development

You can run the Agent in development without any setup. Start the Agent daemon
as follows:

    ~/w/pdagent/bin$ ./pdagentd.py

When run in development the daemon automatically creates a `tmp` directory
inside the project where it stores its various work files.

Similarly, you can use the `pd-send` command immediately.

```
~/w/pdagent/bin$ ./pd-send -h
usage: pd-send [-h] -k SERVICE_KEY [-api {V1,V2}] -t
               {trigger,acknowledge,resolve} [-d DESCRIPTION] [-src SOURCE]
               [-s {critical,warning,error,info}] [-cmp COMPONENT] [-g GROUP]
               [-cls PROB_CLASS] [-i INCIDENT_KEY] [-c CLIENT] [-u CLIENT_URL]
               [-f FIELDS] [-q]

Queue up a trigger, acknowledge, or resolve event to PagerDuty.
...
```

Make sure that you have run the daemon at least once so that the `tmp`
directory exists.

You can stop the daemon as follows:

    ~/w/pdagent/bin$ kill `cat ../tmp/pdagentd.pid`


### IDE Setup

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

For development builds, you can perform a full automated clean build of the
Agent with the following steps:

1. Configure signing keys by following the _One-time Setup_ instructions in
`build-linux/howto.txt`.

2. Run the following commands:

        scons --clean
        scons local-repo gpg-home=build-linux/gnupg

    Note that this will spin up multiple virtual machines using Vagrant to run
    tests and perform builds on.

3. Run integration tests on the packages as follows:

    (i) Edit the file `pdagenttestinteg/util.sh` and change the line
    `SVC_KEY=CHANGEME` to a real PagerDuty Service API Key suitable for testing.

    (ii) Run the command:

        scons test-integration

    This will run the integration tests on the various VMs using the packages
    built in the previous step. Note that the tests will trigger and resolve
    some incidents when they run.


If you want to build packages by hand, follow the instructions in
`build-linux/howto.txt`.

Similarly, you can check the SCons targets using `scons -h` for instructions on
performing specific builds tasks and on specific VMs.

#### Some helpful scripts

```
scripts/rev_pkgs.sh
```

This will remove the installed pdagent packages from the vagrant build machines, `agent-minimal-centos65` and `agent-minimal-ubuntu1204`, and run `scons local-repo gpg-home=build-linux/gnupg` to install them again.  Run this anytime you revise a package artifact like `build-linux/deb/postinst`.

```
scripts/kill_pids.sh
```

This will kill stray pdagent processes and cleanup the pidfile on all vagrant machines.  Run this
if your changes are causing integration tests to fail due to improper process managment via `service` or `systemctl`.

```
scripts/setup_upgrade_test.sh
```

This will vagrant destroy, up and install the latest public repo pdagent package on machines for upgrade testing via `scons test-integration`.

### Release Packages

The steps here and the project scons targets are written assuming that S3 is
used to host the package repository. If you use other methods, please modify
the relevant steps.


#### S3 Setup:

1. Install **s3cmd** from http://s3tools.org/download. This should involve:

        python setup.py install

    or, for a custom location, something like:

        python setup.py install --prefix=~/opt/

2. Configure it by running `s3cmd --configure`.

3. In the S3 related build commands below, remember to replace $S3_BUCKET with
`s3://<your_bucket_name>` or `s3://<your_bucket_name>/<path>` depending on how
you host your repository.


#### Release build, test & upload:

Before you start: did you remember to commit the new Agent version?

1. Ensure your `pdagent` checkout is clean. Either start with a fresh git clone
or:
    - Destroy any existing Vagrant VMs using `vagrant destroy` or `scons
destroy-virt`
    - Use `git clean -dxf` to remove all ignored files
    - Use `git reset`/`git checkout`/etc to ensure no local changes


2. Copy the release GPG signing keys to the `pdagent` project directory so that
the VMs can access it. (via `/vagrant/...`)

        cp -r /path/to/pd-release-keys/gpg-* .

    This should copy two directories `gpg-deb` and `gpg-rpm`


3. Sync the current contents of the packages repo down from S3:

        scons sync-from-remote-repo repo-root=$S3_BUCKET

        cp -r target target-orig


4. Build the packages:

    (a) Ubuntu:

        vagrant up agent-minimal-ubuntu1204
        vagrant ssh agent-minimal-ubuntu1204

        sh /vagrant/build-linux/make_deb.sh /vagrant/gpg-deb /vagrant/target

    This relies on `/vagrant` in the VM being a mount of the pdagent project
    directory.

    Enter the GPG key passphrase when prompted. Exit from the VM when done.

    (b) CentOS:

        vagrant up agent-minimal-centos65
        vagrant ssh agent-minimal-centos65

        sh /vagrant/build-linux/make_rpm.sh /vagrant/gpg-rpm /vagrant/target

    Enter the GPG key passphrase when prompted. Exit from the VM when done.


5. Verify that the new packages are on the host machine in the `target`
directory.

        diff -qr target-orig target


6. Prepare keys for integration testing:

        mkdir ./target/tmp
        gpg --homedir=./gpg-deb --export --armor > ./target/tmp/GPG-KEY-pagerduty
        gpg --homedir=./gpg-rpm --export --armor > ./target/tmp/GPG-KEY-RPM-pagerduty


7. Run the integration tests on clean VMs. (use `vagrant destroy`, edit the
service key in `util.sh`, and run `scons test-integration`)



8. Sync the packages repo back up to S3:

        scons sync-to-remote-repo repo-root=$S3_BUCKET


9. Optionally, tag your release in git:

        git tag vX.Y
        git push origin --tags

#License
Copyright (c) 2013-2014, PagerDuty, Inc. <info@pagerduty.com>
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.
  * Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.
  * Neither the name of the copyright holder nor the
    names of its contributors may be used to endorse or promote products
    derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
