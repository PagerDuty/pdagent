wget -O - https://packages.pagerduty.com/GPG-KEY-pagerduty | sudo apt-key add -
sudo sh -c 'echo "deb https://packages.pagerduty.com/pdagent deb/" >/etc/apt/sources.list.d/pdagent.list'
sudo apt-get update
sudo apt-get -y install pdagent
