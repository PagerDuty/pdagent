#!/bin/bash
# Usage: ./scripts/run-integration-tests.sh <ubuntu OR centos> <test_file>

OS=$1
TEST_FILE=$2
make build-${OS}
if [ $OS == "ubuntu" ]
then
    docker run -d --privileged -v /sys/fs/cgroup:/sys/fs/cgroup:ro -it pdagent-ubuntu
elif [ $OS == 'centos' ]
then
    docker run -d -p 5000:80 --privileged=true --tmpfs /tmp --tmpfs /run -v /sys/fs/cgroup:/sys/fs/cgroup:ro -it pdagent-centos 
fi
docker exec -it $(docker ps -q -f ancestor=pdagent-${OS}) /bin/bash ./pdagenttestinteg/${TEST_FILE}
