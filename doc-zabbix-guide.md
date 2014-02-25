# How to Integrate Zabbix with PagerDuty


## Introduction

SAME AS CURRENT GUIDE


## Setting up the PagerDuty / Zabbix integration

### In PagerDuty:

SAME AS CURRENT GUIDE


### In Zabbix:

UPDATED STEP 1:
	
- Install the PagerDuty Agent as described in [Agent Installation Guide]


REPLACE STEPS 2,3,4 & 5 WITH:

- Make a soft-link to the `pd-zabbix` command line script provided by PagerDuty
  Agent in Zabbix's `AlertScriptsPath` directory.  For example, if the Zabbix
  alert script path is `/etc/zabbix/alert.d`, you can make the soft-link with
  the command:

        sudo ln -s /usr/bin/pd-zabbix /etc/zabbix/alert.d/

  The default `AlertScriptsPath` is usually `/etc/zabbix/alert.d` or
  `/usr/local/share/zabbix/alertscripts` but it can be changed.  If you don’t
  know your path, check your `zabbix_server.conf` file.  If this path is not
  set, check the Zabbix manual for the default path for your version of Zabbix.


UPDATED STEP 11:

- Enter "pd-zabbix" for Script Name


