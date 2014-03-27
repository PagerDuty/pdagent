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

### Release Packages

The build supports uploading to and downloading from your remote repository.
Remote location types supported are:

* S3: You will need to:
    1. Install **s3cmd** from http://s3tools.org/download.
    2. Configure it by running `s3cmd --configure`.
    3. In your scons commands, use `s3://<your_bucket_name>` or
       `s3://<your_bucket_name>/<path>` (depending on how you host your
        repository) as your repository root.

To build & upload packages for release, perform the following steps:

1. Bring up clean VMs. (`vagrant destroy` followed by `vagrant up`)

2. Copy the release GPG signing keys so that it is accessible in the VMs. You
can either copy/link them under the `pdagent` project directory so that the VMs
can access them via `/vagrant/...` or you can copy them into the VMs.

3. Sync the current contents of the packages repo down from S3:

        scons sync-from-remote-repo repo-root=s3://bucketname/pdagent

4. Build the packages:

        vagrant ssh agent-minimal-ubuntu1204

        sh /vagrant/build-linux/make_deb.sh /path/to/prod/gpg/home /vagrant/target
        logout

    Enter the GPG key passphrase when prompted.

    Repeat for *rpm*:

        vagrant ssh agent-minimal-centos65

        sh /vagrant/build-linux/make_rpm.sh /path/to/prod/gpg/home /vagrant/target
        logout

5. Verify that the new packages are on the host machine in the `target`
directory.

6. Run the integration tests as shown earlier. (edit the service key in
`util.sh` and run `scons test-integration`)

7. Sync the packages repo back up to S3:

        scons sync-to-remote-repo repo-root=s3://bucketname/pdagent
