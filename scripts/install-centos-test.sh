set -e

sudo sh -c 'cat >/etc/yum.repos.d/pdagent.repo <<EOF
[pdagent]
name=PDAgent
baseurl=https://packages.pagerduty.com/pdagent/rpm
enabled=1
gpgcheck=1
gpgkey=https://packages.pagerduty.com/GPG-KEY-RPM-pagerduty
EOF'

sudo yum install -y pdagent pdagent-integrations

pd-send -k $PD_SERVICE_KEY -t trigger -d "Server is on fire" -i server.fire
