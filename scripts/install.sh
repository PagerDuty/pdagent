#!/bin/bash

set +e

. ./make_common.env

_VERSION=$(grep '__version__\s*=\s*".*"' ${DOCKER_WORKDIR}/pdagent/__init__.py \
    | cut -d \" -f2)
if [ -z "$_VERSION" ]; then
    echo "Could not find Agent version in source."
    exit 1
fi

echo "= Installing version ${_VERSION}"

OS=$1
if [[ $OS == "ubuntu" ]]
then
    echo "= Installing for Ubuntu"
    dpkg -i ${DOCKER_WORKDIR}/target/deb/pdagent_${_VERSION}_all.deb
elif [[ $OS == "centos" ]]
then
    echo "= Installing for CentOS"
    rpm --import ${DOCKER_WORKDIR}/target/tmp/GPG-KEY-RPM-pagerduty
    yum install -y ${DOCKER_WORKDIR}/target/rpm/pdagent-${_VERSION}-1.noarch.rpm
else
    echo "Error: Expected 'ubuntu' or 'centos' as first argument"
    exit 1
fi
