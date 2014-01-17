#
# Installs the agent from the rpm package.
#

# only run test on redhat installations.
[ -e /etc/redhat-release ] || exit 0

. $(dirname $0)/util.sh

set -e
set -x

# install agent.
sudo rpm -i /vagrant/build-linux/target/pdagent-0.1-1.noarch.rpm

# check installation status.
which $BIN_PD_SEND
python -c "import pdagent; print pdagent.__file__"

# check that agent has started up.
test -n "$(agent_pid)"
