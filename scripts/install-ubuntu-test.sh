set -e

apt-get update
sudo apt-get install apt-transport-https wget
printf "\ninstalled the basics\n"

wget -O - https://packages.pagerduty.com/GPG-KEY-pagerduty | sudo apt-key add -
sudo sh -c 'echo "deb https://packages.pagerduty.com/pdagent deb/" >/etc/apt/sources.list.d/pdagent.list'
apt-get update
sudo apt-get install pdagent pdagent-integrations -y
printf "\ninstalled pdagent\n"

pd-send -k $PD_SERVICE_KEY -t trigger -d "Server is on fire" -i server.fire
printf "\nsent test event to ${PD_SERVICE_KEY}\n"
