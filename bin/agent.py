#!/usr/bin/python
'''
    PagerDuty
    www.pagerduty.com
    ----
    Monitoring system agent for PagerDuty integration.

    See LICENSE.TXT for licensing details.
'''


### BEGIN INIT INFO
# Provides:          pd-agent
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start PagerDuty Agent at boot time
# Description:       Enable PagerDuty Agent daemon process.
### END INIT INFO


# standard python modules
import logging.handlers
import os
import sched
import sys
import time
import json
import urllib2


# Check Python version.
if int(sys.version_info[1]) <= 3:
    print 'You are using an outdated version of Python.' \
        ' Please update to v2.4 or above (v3 is not supported).'
    sys.exit(1)


try:
    import pdagent.config
except ImportError:
    # Fix up for dev layout
    import sys
    from os.path import realpath, dirname
    sys.path.append(dirname(dirname(realpath(__file__))))
    import pdagent.config


# Custom modules
from pdagent.daemon import Daemon
from pdagent.pdqueue import PDQueue, EmptyQueue
from pdagent.filelock import FileLock
from pdagent.backports.ssl_match_hostname import CertificateError
from pdagent.constants import \
    EVENT_CONSUMED, EVENT_NOT_CONSUMED, EVENT_BAD_ENTRY, \
    EVENTS_API_BASE


# Config handling
agentConfig = pdagent.config.get_main_config()


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
        return EVENT_BAD_ENTRY
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
    except CertificateError:
        mainLogger.error(
            "Server certificate validation error while flushing queue:",
            exc_info=True
            )
    except IOError:
        mainLogger.error("I/O error while flushing queue:", exc_info=True)
    except:
        mainLogger.error("Error while flushing queue:", exc_info=True)

    # clean up if required.
    secondsSinceCleanup = int(time.time()) - agent.lastCleanupTimeSec
    if secondsSinceCleanup >= agentConfig['cleanup_freq_sec']:
        try:
            pdQueue.cleanup()
        except:
            mainLogger.error("Error while cleaning up queue:", exc_info=True)
        agent.lastCleanupTimeSec = int(time.time())

    # schedule next tick.
    sc.enter(agentConfig['check_freq_sec'], 1, tick, (sc,))


def _ensureWritableDirectories(make_missing_dir, *directories):
    problemDirectories = []
    for directory in set(directories):
        if make_missing_dir and not os.path.exists(directory):
            try:
                os.mkdir(directory)
            except OSError:
                pass  # handled in the check immediately below
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
            # no codename for FreeBSD
            systemStats['fbsdV'] = ('freebsd', version, '')

        mainLogger.info('System: ' + str(systemStats))

        mainLogger.debug('Creating tick instance')

        # Schedule the tick
        mainLogger.info('check_freq_sec: %s', agentConfig['check_freq_sec'])
        s = sched.scheduler(time.time, time.sleep)
        tick(s)  # start immediately
        s.run()

# Control of daemon
if __name__ == '__main__':

    conf_dirs = pdagent.config.get_conf_dirs()
    pidfile_dir = conf_dirs['pidfile_dir']
    log_dir = conf_dirs['log_dir']
    data_dir = conf_dirs['data_dir']
    outqueue_dir = conf_dirs["outqueue_dir"]

    problemDirectories = _ensureWritableDirectories(
        pdagent.config.is_dev_layout(),  # don't create directories in production
        pidfile_dir, log_dir, data_dir, outqueue_dir
        )
    if problemDirectories:
        for d in problemDirectories:
            print 'Directory %s: cannot create or is not writable' % d
        print 'Agent will now quit'
        sys.exit(1)

    # Logging
    logFile = os.path.join(log_dir, 'pd-agent.log')

    # 10MB files
    handler = logging.handlers.RotatingFileHandler(
        logFile, maxBytes=10485760, backupCount=5
        )

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    handler.setFormatter(formatter)

    mainLogger = logging.getLogger('main')
    mainLogger.setLevel(agentConfig['log_level'])
    mainLogger.addHandler(handler)

    mainLogger.info('--')
    mainLogger.info('pd-agent started')  # TODO: log agent version
    mainLogger.info('--')

    mainLogger.info('event_api_url: %s', agentConfig['event_api_url'])

    from pdagent.argparse import ArgumentParser
    description = "PagerDuty Agent daemon process."
    parser = ArgumentParser(description=description)
    parser.add_argument(
        'action', choices=['start', 'stop', 'restart', 'status']
        )
    parser.add_argument(
        "--clean", action="store_true", dest="clean",
        help="Remove old pid file"
        )

    args = parser.parse_args()

    pidFile = os.path.join(pidfile_dir, 'pd-agent.pid')

    if os.access(pidfile_dir, os.W_OK) == False:
        print 'Unable to write the PID file at ' + pidFile
        print 'Agent will now quit'
        sys.exit(1)

    mainLogger.info('PID file: %s', pidFile)

    # queue to work on.
    pdQueue = PDQueue(queue_dir=outqueue_dir, lock_class=FileLock)

    # Daemon instance from agent class
    daemon = agent(pidFile)

    # Helper method for some control options
    def _getDaemonPID():
        try:
            pf = file(pidFile, 'r')
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
            print 'pd-agent is running as pid %s.' % pid
        else:
            print 'pd-agent is not running.'

    else:
        print 'Unknown command'
        sys.exit(1)

    sys.exit(0)
