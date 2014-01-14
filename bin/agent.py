#!/usr/bin/python
'''
    PagerDuty
    www.pagerduty.com
    ----
    Monitoring system agent for PagerDuty integration.

    See LICENSE.TXT for licensing details.
'''

# standard python modules
import logging.handlers
import os
import sched
import sys
import time
import json
import socket
import urllib2
from urllib2 import HTTPError, URLError


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
from pdagent.pdqueue import EmptyQueue
from pdagent.backports.ssl_match_hostname import CertificateError
from pdagent.constants import \
    EVENT_CONSUMED, EVENT_NOT_CONSUMED, EVENT_BAD_ENTRY,\
    EVENT_BACKOFF_SVCKEY_BAD_ENTRY, EVENT_BACKOFF_SVCKEY_NOT_CONSUMED, \
    EVENT_STOP_ALL, EVENTS_API_BASE


# Config handling
agentConfig = pdagent.config.load_agent_config()
mainConfig = agentConfig.get_main_config()


def send_event(json_event_str):
    from pdagent import httpswithverify
    request = urllib2.Request(EVENTS_API_BASE)
    request.add_header("Content-type", "application/json")
    request.add_data(json_event_str)

    status_code, result_str = None, None
    try:
        response = httpswithverify.urlopen(
            request,
            timeout=mainConfig["send_event_timeout_sec"])
        status_code = response.getcode()
        result_str = response.read()
    except HTTPError as e:
        # the http error is structured similar to an http response.
        status_code = e.getcode()
        result_str = e.read()
    except CertificateError:
        mainLogger.error(
            "Server certificate validation error while sending event:",
            exc_info=True)
        return EVENT_STOP_ALL
    except URLError as e:
        if isinstance(e.reason, socket.timeout):
            mainLogger.error("Timeout while sending event:", exc_info=True)
            # This could be real issue with PD, or just some anomaly in
            # processing this service key or event. We'll retry this service key
            # a few more times, and then decide that this event is possibly a
            # bad entry.
            return EVENT_BACKOFF_SVCKEY_BAD_ENTRY
        else:
            mainLogger.error(
                "Error establishing a connection for sending event:",
                exc_info=True)
            return EVENT_NOT_CONSUMED
    except IOError:
        mainLogger.error("Error while sending event:", exc_info=True)
        return EVENT_NOT_CONSUMED

    try:
        result = json.loads(result_str)
    except:
        mainLogger.warning(
            "Error reading response data while sending event:",
            exc_info=True)
        result = {}
    if result.get("status") == "success":
        mainLogger.info("incident_key =", result.get("incident_key"))
    else:
        mainLogger.error("Error sending event %s; Error code: %d, Reason: %s" %
            (json_event_str, status_code, result_str))

    if status_code < 300:
        return EVENT_CONSUMED
    elif status_code == 403:
        # We are getting throttled! We'll retry this service key a few more
        # times, but never consider this event as erroneous.
        return EVENT_BACKOFF_SVCKEY_NOT_CONSUMED
    elif status_code >= 400 and status_code < 500:
        return EVENT_BAD_ENTRY
    elif status_code >= 500 and status_code < 600:
        # Hmm. Could be server-side problem, or a bad entry.
        # We'll retry this service key a few times, and then decide that this
        # event is possibly a bad entry.
        return EVENT_BACKOFF_SVCKEY_BAD_ENTRY
    else:
        # anything 3xx and >= 5xx
        return EVENT_NOT_CONSUMED


def tick(sc):
    # flush the event queue.
    mainLogger.info("Flushing event queue")
    try:
        pdQueue.flush(send_event)
    except EmptyQueue:
        mainLogger.info("Nothing to do - queue is empty!")
    except IOError:
        mainLogger.error("I/O error while flushing queue:", exc_info=True)
    except:
        mainLogger.error("Error while flushing queue:", exc_info=True)

    # clean up if required.
    secondsSinceCleanup = int(time.time()) - agent.lastCleanupTimeSec
    if secondsSinceCleanup >= mainConfig['cleanup_freq_sec']:
        try:
            pdQueue.cleanup(mainConfig['cleanup_before_sec'])
        except:
            mainLogger.error("Error while cleaning up queue:", exc_info=True)
        agent.lastCleanupTimeSec = int(time.time())

    # schedule next tick.
    sc.enter(mainConfig['check_freq_sec'], 1, tick, (sc,))


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
        mainLogger.info('check_freq_sec: %s', mainConfig['check_freq_sec'])
        s = sched.scheduler(time.time, time.sleep)
        tick(s)  # start immediately
        s.run()

# Control of daemon
if __name__ == '__main__':

    conf_dirs = agentConfig.get_conf_dirs()
    pidfile_dir = conf_dirs['pidfile_dir']
    log_dir = conf_dirs['log_dir']
    data_dir = conf_dirs['data_dir']
    outqueue_dir = conf_dirs["outqueue_dir"]
    db_dir = conf_dirs["db_dir"]

    problemDirectories = _ensureWritableDirectories(
        agentConfig.is_dev_layout(),  # don't create directories in production
        pidfile_dir, log_dir, data_dir, outqueue_dir, db_dir
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
    mainLogger.setLevel(mainConfig['log_level'])
    mainLogger.addHandler(handler)

    mainLogger.info('--')
    mainLogger.info('pd-agent started')  # TODO: log agent version
    mainLogger.info('--')

    mainLogger.info('event_api_url: %s', mainConfig['event_api_url'])

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
    pdQueue = agentConfig.get_queue()

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
