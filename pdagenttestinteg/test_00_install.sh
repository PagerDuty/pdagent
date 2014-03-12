#
# Installs the agent.
#
# Copyright (c) 2013-2014, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the copyright holder nor the
#     names of its contributors may be used to endorse or promote products
#     derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

. $(dirname $0)/util.sh

set -e
set -x

# install agent.
case $(os_type) in
  debian)
    sudo apt-key add /vagrant/target/tmp/GPG-KEY-pagerduty
    sudo sh -c 'echo "deb file:///vagrant/target deb/" \
      >/etc/apt/sources.list.d/pdagent.list'
    sudo apt-get update

    if [ -z "$UPGRADE_FROM_VERSION" ]; then
        sudo apt-get install -y pdagent
    else
        sudo apt-get install -y pdagent=$UPGRADE_FROM_VERSION
        # to upgrade pdagent pkg, run `apt-get install`, not `apt-get upgrade`.
        # 'install' updates one pkg, 'upgrade' updates all installed pkgs.
        sudo apt-get install -y pdagent
    fi
    ;;
  redhat)
    sudo sh -c 'cat >/etc/yum.repos.d/pdagent.repo <<EOF
[pdagent]
name=PDAgent
baseurl=file:///vagrant/target/rpm
enabled=1
gpgcheck=1
gpgkey=file:///vagrant/target/tmp/GPG-KEY-pagerduty
EOF'

    if [ -z "$UPGRADE_FROM_VERSION" ]; then
        sudo yum install -y pdagent
    else
        sudo yum install -y pdagent-$UPGRADE_FROM_VERSION
        sudo yum upgrade -y pdagent
    fi
    ;;
  *)
    echo "Unknown os_type " $(os_type) >&2
    exit 1
esac

# check installation status.
which $BIN_PD_SEND
python -c "import pdagent; print pdagent.__file__"

# check that agent has started up.
test -n "$(agent_pid)"

# check that there is an agent id file created.
test -e $DATA_DIR/agent_id.txt

# check permissions of files created by agent
test `stat -c %a $DATA_DIR/agent_id.txt` -eq "644"
test `stat -c %a $LOG_FILE` -eq "644"

