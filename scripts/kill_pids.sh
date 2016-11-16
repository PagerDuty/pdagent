vagrant ssh agent-minimal-centos65 -c 'sudo pkill -9 pdagent; sudo rm /var/run/pdagent/pdagentd.pid '
vagrant ssh agent-minimal-ubuntu1204 -c 'sudo pkill -9 pdagent; sudo rm /var/run/pdagent/pdagentd.pid'
vagrant ssh agent-minimal-ubuntu1404 -c 'sudo pkill -9 pdagent; sudo rm /var/run/pdagent/pdagentd.pid'
vagrant ssh agent-minimal-ubuntu1604 -c 'sudo pkill -9 pdagent; sudo rm /var/run/pdagent/pdagentd.pid'
