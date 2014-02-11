# How to Integrate Zabbix with PagerDuty


## Introduction

Zabbix is a very powerful ...

PagerDuty extends ...

This guide ...

## Setting up the PagerDuty / Zabbix integration

### In PagerDuty:

Create a “Generic API system” service:

...


### In Zabbix:
	
1. Install the PagerDuty Agent as described in [Agent Installation Guide]


REPLACE STEPS 2,3,4 & 5 WITH:

2. Make a soft-link to the `pd-zabbix` tool in Zabbix's AlertScriptsPath
directory.  By default, the AlertScriptsPath is set to be /etc/zabbix/alert.d;
however, it can be changed. If you don’t know your path, check your
zabbix_server.conf file.

    sudo ln -s /usr/bin/pd-zabbix /etc/zabbix/alert.d/


11. Enter "pd-zabbix" for Script Name


