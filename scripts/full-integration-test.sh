# Usage: ./scripts/run-console.sh <ubuntu OR centos>

OS=$1
make build-${OS}
if [ $OS == "ubuntu" ]
then
    docker stop pdagent-ubuntu
    docker rm pdagent-ubuntu
    docker run --name pdagent-ubuntu  -d --privileged -v /sys/fs/cgroup:/sys/fs/cgroup:ro -it pdagent-ubuntu
elif [ $OS == 'centos' ]
then
    docker stop pdagent-centos
    docker rm pdagent-centos
    docker run -d --privileged=true --tmpfs /tmp --tmpfs /run -v /sys/fs/cgroup:/sys/fs/cgroup:ro -it pdagent-centos
fi

_PID=$(docker ps -q -f ancestor=pdagent-${OS})
docker exec $_PID /bin/bash /usr/share/pdagent/scripts/install.sh $OS

if [ -z $TEST_FILE ]
then
    docker exec $_PID /bin/bash /usr/share/pdagent/integration_tests/run-tests.sh 
else
    docker exec -it $_PID /bin/bash ./integration_tests/${TEST_FILE}
fi

