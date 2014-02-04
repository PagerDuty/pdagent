#!/bin/sh
#
# chkconfig: 2345 99 1
# description: PagerDuty Agent daemon process.
#

### BEGIN INIT INFO
# Provides:          pdagentd
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: PagerDuty Agent
# Description:       PagerDuty Agent daemon process.
### END INIT INFO

sudo -u pdagent /usr/bin/pdagentd.py "$@"
