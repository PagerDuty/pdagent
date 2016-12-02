sudo sh -c 'cat >/etc/yum.repos.d/pdagent.repo <<EOF
[pdagent]
name=PDAgent
baseurl=https://packages.pagerduty.com/pdagent/rpm
enabled=1
gpgcheck=1
gpgkey=https://packages.pagerduty.com/GPG-KEY-RPM-pagerduty
EOF'
sudo yum -y install pdagent
