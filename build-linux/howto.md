# Linux Build Instructions

These instructions assume you're running this on a Mac with Docker installed,
and that the project directory ends up mounted in the VM at
`/usr/share/pdagent`. (this should happen automatically)

## One-time setup of Development GPG keys:

To build Linux packages, you will need GPG v1 keys to sign the packages.  Do the following:

```
brew install gpg1
mkdir build-linux/gpg-deb
chmod 700 build-linux/gpg-deb
gpg1 --homedir=build-linux/gpg-deb --gen-key
```

For key generation use the suggested defaults and *no passphrase*. (when
asked to enter a passphrase, just press *Enter*)

If you use a different `homedir`, please adjust the `homedir` parameter in
the following instructions accordingly. Specifically, the `make ubuntu` command and other like build automations assume the value to be `gpg-deb`.

## Docker

Docker has issues with systemd and so, if you want to install and test the package, you will need to build the package with `SKIP_SYSTEMD` set to `true` in `build-linux/make_common.env`. However, for any package you publish, make sure `SKIP_SYSTEMD` is set to `false`.

## Ubuntu

Building the .deb:

```
make ubuntu
```

Install & test the .deb:
```
docker run -it pdagent-ubuntu /bin/bash

sudo apt-key add /usr/share/pdagent/target/tmp/GPG-KEY-pagerduty
sudo sh -c 'echo "deb file:///usr/share/pdagent/target deb/" \
  >/etc/apt/sources.list.d/pdagent.list'
sudo apt-get update
sudo apt-get install pdagent
sudo service pdagent status
which pd-send
python -c "import pdagent; print pdagent.__file__"
```

Uninstall & test cleanup:
```
sudo apt-get --yes remove pdagent

# ensure that artifacts are no longer present
sudo service pdagent status
which pd-send
```

Rerun the test commands to ensure files are gone

## CentOS / RHEL

Building the .rpm:
```
make centos
```

Install & test the .rpm:
```
docker run -it pdagent-centos /bin/bash

sudo sh -c 'cat >/etc/yum.repos.d/pdagent.repo <<EOF
[pdagent]
name=PDAgent
baseurl=file:///usr/share/pdagent/target/rpm
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/pdagent/target/tmp/GPG-KEY-RPM-pagerduty
EOF'

sudo yum install -y pdagent
sudo service pdagent status
which pd-send
python -c "import pdagent; print pdagent.__file__"
```

Uninstall & test cleanup:
```
sudo yum remove -y pdagent

# ensure that artifacts are no longer present
sudo service pdagent status
which pd-send
```
