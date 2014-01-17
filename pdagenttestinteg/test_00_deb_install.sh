#
# Installs the agent from the deb package.
#

# only run test on debian installations.
[ -e /etc/debian_version ] || exit 0

. $(dirname $0)/util.sh

set -e
set -x

# install agent.
sudo dpkg -i /vagrant/build-linux/target/pdagent_0.1_all.deb

# check installation status.
which $BIN_PD_SEND
python -c "import pdagent; print pdagent.__file__"

# check that agent has started up.
test -n "$(agent_pid)"
