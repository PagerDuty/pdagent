#!/usr/bin/env python
'''
    PagerDuty
    www.pagerduty.com
    ----
    Monitoring system agent for PagerDuty integration.

    See LICENSE.TXT for licensing details.
'''

import logging
import logging.handlers

# General config
agentConfig = {}
agentConfig['logging'] = logging.INFO
agentConfig['checkFreq'] = 60

agentConfig['version'] = '0.1'

rawConfig = {}

# Check we're not using an old version of Python. Do this before anything else
# We need 2.4 above because some modules (like subprocess) were only introduced in 2.4.
import sys
if int(sys.version_info[1]) <= 3:
    print 'You are using an outdated version of Python. Please update to v2.4 or above (v3 is not supported). For newer OSs, you can update Python without affecting your system install. See http://blog.boxedice.com/2010/01/19/updating-python-on-rhelcentos/ If you are running RHEl 4 / CentOS 4 then you will need to compile Python manually.'
    sys.exit(1)

# Core modules
import ConfigParser
import glob
import os
import re
import sched
import time

# After the version check as this isn't available on older Python versions
# and will error before the message is shown
import subprocess

# Calculate project directory
proj_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Fix classpath to reach custom modules
sys.path.append(proj_dir)

# Custom modules
from pdagent.daemon import Daemon

# Config handling
try:
    config = ConfigParser.ConfigParser()

    configPath = os.path.join(proj_dir, "conf", "config.cfg")

    if os.access(configPath, os.R_OK) == False:
        print 'Unable to read the config file at ' + configPath
        print 'Agent will now quit'
        sys.exit(1)

    config.read(configPath)

    # Core config
    agentConfig['sdUrl'] = config.get('Main', 'sd_url')

    if agentConfig['sdUrl'].endswith('/'):
        agentConfig['sdUrl'] = agentConfig['sdUrl'][:-1]

    agentConfig['agentKey'] = config.get('Main', 'agent_key')

    # Tmp path
    agentConfig['tmpDirectory'] = os.path.join(proj_dir, "bin") # default which may be overriden in the config later

    agentConfig['pidfileDirectory'] = agentConfig['tmpDirectory']

    # Plugin config
    if config.has_option('Main', 'plugin_directory'):
        agentConfig['pluginDirectory'] = config.get('Main', 'plugin_directory')

    # Optional config
    # Also do not need to be present in the config file (case 28326).
    if config.has_option('Main', 'logging_level'):
        # Maps log levels from the configuration file to Python log levels
        loggingLevelMapping = {
            'debug'    : logging.DEBUG,
            'info'     : logging.INFO,
            'error'    : logging.ERROR,
            'warn'     : logging.WARN,
            'warning'  : logging.WARNING,
            'critical' : logging.CRITICAL,
            'fatal'    : logging.FATAL,
        }

        customLogging = config.get('Main', 'logging_level')

        try:
            agentConfig['logging'] = loggingLevelMapping[customLogging.lower()]

        except KeyError, ex:
            agentConfig['logging'] = logging.INFO

    if config.has_option('Main', 'tmp_directory'):
        agentConfig['tmpDirectory'] = config.get('Main', 'tmp_directory')

    if config.has_option('Main', 'pidfile_directory'):
        agentConfig['pidfileDirectory'] = config.get('Main', 'pidfile_directory')

except ConfigParser.NoSectionError, e:
    print 'Config file not found or incorrectly formatted'
    print 'Agent will now quit'
    sys.exit(1)

except ConfigParser.ParsingError, e:
    print 'Config file not found or incorrectly formatted'
    print 'Agent will now quit'
    sys.exit(1)

except ConfigParser.NoOptionError, e:
    print 'There are some items missing from your config file, but nothing fatal'

# Check to make sure the default config values have been changed (only core config values)
if agentConfig['sdUrl'] == 'http://example.serverdensity.com' or agentConfig['agentKey'] == 'keyHere':
    print 'You have not modified config.cfg for your server'
    print 'Agent will now quit'
    sys.exit(1)

# Check to make sure sd_url is in correct
if (re.match('http(s)?(\:\/\/)[a-zA-Z0-9_\-]+\.(serverdensity.com)', agentConfig['sdUrl']) == None) \
   and (re.match('http(s)?(\:\/\/)[a-zA-Z0-9_\-]+\.(serverdensity.io)', agentConfig['sdUrl']) == None):
    print 'Your sd_url is incorrect. It needs to be in the form https://example.serverdensity.com or https://example.serverdensity.io'
    print 'Agent will now quit'
    sys.exit(1)

for section in config.sections():
    rawConfig[section] = {}

    for option in config.options(section):
        rawConfig[section][option] = config.get(section, option)


def tick(sc):
    mainLogger.info("Tick!")
    sc.enter(agentConfig['checkFreq'], 1, tick, (sc,))

# Override the generic daemon class to run our checks
class agent(Daemon):

    def run(self):
        mainLogger.debug('Collecting basic system stats')

        # Get some basic system stats to post back for development/testing
        import platform
        systemStats = {'machine': platform.machine(), 'platform': sys.platform, 'processor': platform.processor(), 'pythonV': platform.python_version()}

        if sys.platform == 'linux2':
            systemStats['nixV'] = platform.dist()

        elif sys.platform == 'darwin':
            systemStats['macV'] = platform.mac_ver()

        elif sys.platform.find('freebsd') != -1:
            version = platform.uname()[2]
            systemStats['fbsdV'] = ('freebsd', version, '') # no codename for FreeBSD

        mainLogger.info('System: ' + str(systemStats))

        mainLogger.debug('Creating tick instance')

        # Schedule the tick
        mainLogger.info('checkFreq: %s', agentConfig['checkFreq'])
        s = sched.scheduler(time.time, time.sleep)
        tick(s) # start immediately (case 28315)
        s.run()

# Control of daemon
if __name__ == '__main__':

    # Logging
    logFile = os.path.join(agentConfig['tmpDirectory'], 'sd-agent.log')

    if os.access(agentConfig['tmpDirectory'], os.W_OK) == False:
        print 'Unable to write the log file at ' + logFile
        print 'Agent will now quit'
        sys.exit(1)

    handler = logging.handlers.RotatingFileHandler(logFile, maxBytes=10485760, backupCount=5) # 10MB files
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    handler.setFormatter(formatter)

    mainLogger = logging.getLogger('main')
    mainLogger.setLevel(agentConfig['logging'])
    mainLogger.addHandler(handler)

    mainLogger.info('--')
    mainLogger.info('sd-agent %s started', agentConfig['version'])
    mainLogger.info('--')

    mainLogger.info('sd_url: %s', agentConfig['sdUrl'])
    mainLogger.info('agent_key: %s', agentConfig['agentKey'])

    from pdagent.argparse import ArgumentParser
    description="PagerDuty Agent daemon process."
    parser = ArgumentParser(description=description)
    parser.add_argument('action', choices=['start','stop','restart','status'])
    parser.add_argument("--clean", action="store_false", dest="clean",
            help="Remove old pid file")

    args = parser.parse_args()

    pidFile = os.path.join(agentConfig['pidfileDirectory'], 'sd-agent.pid')

    if os.access(agentConfig['pidfileDirectory'], os.W_OK) == False:
        print 'Unable to write the PID file at ' + pidFile
        print 'Agent will now quit'
        sys.exit(1)

    mainLogger.info('PID: %s', pidFile)

    if args.clean:
        mainLogger.info('--clean')
        try:
            os.remove(pidFile)
        except OSError:
            # Did not find pid file
            pass

    # Daemon instance from agent class
    daemon = agent(pidFile)

    # Control options
    if 'start' == args.action:
        mainLogger.info('Action: start')
        daemon.start()

    elif 'stop' == args.action:
        mainLogger.info('Action: stop')
        daemon.stop()

    elif 'restart' == args.action:
        mainLogger.info('Action: restart')
        daemon.restart()

    elif 'foreground' == args.action:
        mainLogger.info('Action: foreground')
        daemon.run()

    elif 'status' == args.action:
        mainLogger.info('Action: status')

        try:
            pf = file(pidFile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        except SystemExit:
            pid = None

        if pid:
            print 'sd-agent is running as pid %s.' % pid
        else:
            print 'sd-agent is not running.'

    else:
        print 'Unknown command'
        sys.exit(1)

    sys.exit(0)

