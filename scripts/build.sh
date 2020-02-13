#!/bin/bash

OS=$1
if [[ $OS == "ubuntu" ]]
then
    dpkg -i /pd-agent-install/build-linux/release/deb/pdagent_1.6_all.deb
elif [[ $OS == "centos" ]]
then
    rpm --import /pd-agent-install/target/tmp/GPG-KEY-pagerduty
    yum install -y /pd-agent-install/build-linux/release/rpm/pdagent-1.6-1.noarch.rpm
fi
