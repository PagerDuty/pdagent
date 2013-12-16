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
agentConfig['checkFreqSec'] = 60
agentConfig['cleanupFreqSec'] = 60 * 60 * 3  # clean up every 3 hours.

agentConfig['version'] = '0.1'

rawConfig = {}

# Check we're not using an old version of Python. Do this before anything else
# We need 2.4 above because some modules (like subprocess) were only introduced in 2.4.
import sys
if int(sys.version_info[1]) <= 3:
    print 'You are using an outdated version of Python.' \
        ' Please update to v2.4 or above (v3 is not supported).' \
        ' For newer OSs, you can update Python without affecting your system install.' \
        ' See http://blog.boxedice.com/2010/01/19/updating-python-on-rhelcentos/' \
        ' If you are running RHEl 4 / CentOS 4 then you will need to compile Python manually.'
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
import json
import subprocess
import urllib2

# Calculate project directory
proj_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Fix classpath to reach custom modules
sys.path.append(proj_dir)

# Custom modules
from pdagent.daemon import Daemon
from pdagent.pdqueue import PDQueue, EmptyQueue
from pdagent.filelock import FileLock
from pdagent.backports.ssl_match_hostname import CertificateError
from pdagent.constants import \
    EVENT_CONSUMED, EVENT_NOT_CONSUMED, EVENT_CONSUME_ERROR, \
    EVENTS_API_BASE

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
    agentConfig['pdUrl'] = config.get('Main', 'pd_url')

    if agentConfig['pdUrl'].endswith('/'):
        agentConfig['pdUrl'] = agentConfig['pdUrl'][:-1]

    agentConfig['agentKey'] = config.get('Main', 'agent_key')

    # Tmp path
    # default which may be overriden in the config later
    agentConfig['tmpDirectory'] = os.path.join(proj_dir, "tmp")

    agentConfig['pidfileDirectory'] = agentConfig['tmpDirectory']

    agentConfig['queueDirectory'] = os.path.join(proj_dir, "queue")

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

    if config.has_option('Main', 'queue_directory'):
        agentConfig['queueDirectory'] = config.get('Main', 'queue_directory')

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
if agentConfig['pdUrl'] == 'http://example.pagerduty.com' \
        or agentConfig['agentKey'] == 'keyHere':
    print 'You have not modified config.cfg for your server'
    print 'Agent will now quit'
    sys.exit(1)

# Check to make sure pd_url format is correct
if re.match('http(s)?(\:\/\/)[a-zA-Z0-9_\-]+\.(pagerduty.com)', agentConfig['pdUrl']) == None:
    print 'Your pd_url is incorrect. It needs to be in the form https://example.pagerduty.com'
    print 'Agent will now quit'
    sys.exit(1)

for section in config.sections():
    rawConfig[section] = {}

    for option in config.options(section):
        rawConfig[section][option] = config.get(section, option)


def send_event(json_event_str):
    from pdagent import httpswithverify
    request = urllib2.Request(EVENTS_API_BASE)
    request.add_header("Content-type", "application/json")
    request.add_data(json_event_str)

    response = httpswithverify.urlopen(request)
    status_code = response.getcode()
    result = json.loads(response.read())

    incident_key = None
    if result["status"] == "success":
        incident_key = result["incident_key"]
        print "Success! incident_key =", incident_key
    else:
        print "Error! Reason:", str(response)

    if status_code < 300:
        return EVENT_CONSUMED
    elif status_code is 403:
        # we are getting throttled! we'll retry later.
        return EVENT_NOT_CONSUMED
    elif status_code >= 400 and status_code < 500:
        return EVENT_CONSUME_ERROR
    else:
        # anything 3xx and >= 5xx
        return EVENT_NOT_CONSUMED


def tick(sc):
    # flush the event queue.
    mainLogger.info("Flushing event queue")
    try:
        pdQueue.dequeue(send_event)
    except EmptyQueue:
        mainLogger.info("Nothing to do - queue is empty!")
    except CertificateError as e:
        mainLogger.error("Server certificate validation error while flushing queue:", exc_info=True)
    except IOError as e:
        mainLogger.error("I/O error while flushing queue:", exc_info=True)
    except:
        mainLogger.error("Error while flushing queue:", exc_info=True)

    # clean up if required.
    secondsSinceCleanup = int(time.time()) - agent.lastCleanupTimeSec
    if secondsSinceCleanup >= agentConfig['cleanupFreqSec']:
        try:
            pdQueue.cleanup()
        except:
            mainLogger.error("Error while cleaning up queue:", exc_info=True)
        agent.lastCleanupTimeSec = int(time.time())

    # schedule next tick.
    sc.enter(agentConfig['checkFreqSec'], 1, tick, (sc,))


def _ensureWritableDirectories(*directories):
    problemDirectories = []
    for directory in set(directories):
        if not os.path.exists(directory):
            try:
                os.mkdir(directory)
            except OSError:
                pass  # handled in the check for valid existence immediately below
        if os.access(directory, os.W_OK) == False:
            problemDirectories.append(directory)

    return problemDirectories


# Override the generic daemon class to run our checks
class agent(Daemon):

    lastCleanupTimeSec = 0

    def run(self):
        mainLogger.debug('Collecting basic system stats')

        # Get some basic system stats to post back for development/testing
        import platform
        systemStats = {
            'machine': platform.machine(),
            'platform': sys.platform,
            'processor': platform.processor(),
            'pythonV': platform.python_version()
            }

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
        mainLogger.info('checkFreqSec: %s', agentConfig['checkFreqSec'])
        s = sched.scheduler(time.time, time.sleep)
        tick(s) # start immediately (case 28315)
        s.run()

# Control of daemon
if __name__ == '__main__':

    problemDirectories = _ensureWritableDirectories( \
            agentConfig['tmpDirectory'], \
            agentConfig['pidfileDirectory'], \
            agentConfig['queueDirectory'])
    if problemDirectories:
        for d in problemDirectories:
            print 'Directory %s: cannot create or is not writable' % d
        print 'Agent will now quit'
        sys.exit(1)

    tmpDirectory = agentConfig['tmpDirectory']

    # Logging
    logFile = os.path.join(tmpDirectory, 'sd-agent.log')

    # 10MB files
    handler = logging.handlers.RotatingFileHandler(logFile, maxBytes=10485760, backupCount=5)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    handler.setFormatter(formatter)

    mainLogger = logging.getLogger('main')
    mainLogger.setLevel(agentConfig['logging'])
    mainLogger.addHandler(handler)

    mainLogger.info('--')
    mainLogger.info('sd-agent %s started', agentConfig['version'])
    mainLogger.info('--')

    mainLogger.info('pd_url: %s', agentConfig['pdUrl'])
    mainLogger.info('agent_key: %s', agentConfig['agentKey'])

    from pdagent.argparse import ArgumentParser
    description="PagerDuty Agent daemon process."
    parser = ArgumentParser(description=description)
    parser.add_argument('action', choices=['start','stop','restart','status'])
    parser.add_argument("--clean", action="store_true", dest="clean",
            help="Remove old pid file")

    args = parser.parse_args()

    pidFile = os.path.join(agentConfig['pidfileDirectory'], 'sd-agent.pid')

    if os.access(agentConfig['pidfileDirectory'], os.W_OK) == False:
        print 'Unable to write the PID file at ' + pidFile
        print 'Agent will now quit'
        sys.exit(1)

    mainLogger.info('PID: %s', pidFile)

    # queue to work on.
    pdQueue = PDQueue(
            queue_dir=agentConfig["queueDirectory"],
            lock_class=FileLock
            )

    # Daemon instance from agent class
    daemon = agent(pidFile)

    # Helper method for some control options
    def _getDaemonPID():
        try:
            pf = file(pidFile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        except SystemExit:
            pid = None
        return pid

    # Control options
    if args.clean:
        mainLogger.info('--clean')
        try:
            if _getDaemonPID():
                daemon.stop()
            os.remove(pidFile)
        except OSError:
            # Did not find pid file
            pass

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

        pid = _getDaemonPID()
        if pid:
            print 'sd-agent is running as pid %s.' % pid
        else:
            print 'sd-agent is not running.'

    else:
        print 'Unknown command'
        sys.exit(1)

    sys.exit(0)

