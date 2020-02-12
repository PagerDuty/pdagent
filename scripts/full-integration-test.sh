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
docker exec $(docker ps -q -f ancestor=pdagent-${OS}) /bin/bash -c /pd-agent-install/integration_tests/run-tests.sh 
