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
if sys.version_info[0:2] not in ((2, 6), (2, 7)):
    raise SystemExit(
        "Agent requires Python version 2.6 or 2.7.\n" +
        "Agent will now quit"
        )

# Check we're not running as root
if os.geteuid() == 0:
    raise SystemExit(
        "Agent should not be run as root. Use: service pd-agent <command>\n" +
        "Agent will now quit"
        )

try:
    import pdagent.config
except ImportError:
    # Fix up for dev layout
    import sys
    from os.path import realpath, dirname
    sys.path.append(dirname(dirname(realpath(__file__))))
    import pdagent.config


# Custom modules
from pdagent.thirdparty import httpswithverify
from pdagent.thirdparty.daemon import Daemon
from pdagent.pdqueue import EmptyQueueError
from pdagent.thirdparty.ssl_match_hostname import CertificateError
from pdagent.constants import AGENT_VERSION, ConsumeEvent, EVENTS_API_BASE, \
    PHONE_HOME_URI


# Config handling
agentConfig = pdagent.config.load_agent_config()
mainConfig = agentConfig.get_main_config()


def send_event(json_event_str):
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
        main_logger.error(
            "Server certificate validation error while sending event:",
            exc_info=True)
        return ConsumeEvent.STOP_ALL
    except URLError as e:
        if isinstance(e.reason, socket.timeout):
            main_logger.error("Timeout while sending event:", exc_info=True)
            # This could be real issue with PD, or just some anomaly in
            # processing this service key or event. We'll retry this service key
            # a few more times, and then decide that this event is possibly a
            # bad entry.
            return ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
        else:
            main_logger.error(
                "Error establishing a connection for sending event:",
                exc_info=True)
            return ConsumeEvent.NOT_CONSUMED
    except IOError:
        main_logger.error("Error while sending event:", exc_info=True)
        return ConsumeEvent.NOT_CONSUMED

    try:
        result = json.loads(result_str)
    except:
        main_logger.warning(
            "Error reading response data while sending event:",
            exc_info=True)
        result = {}
    if result.get("status") == "success":
        main_logger.info("incident_key =", result.get("incident_key"))
    else:
        main_logger.error("Error sending event %s; Error code: %d, Reason: %s" %
            (json_event_str, status_code, result_str))

    if status_code < 300:
        return ConsumeEvent.CONSUMED
    elif status_code == 403:
        # We are getting throttled! We'll retry this service key a few more
        # times, but never consider this event as erroneous.
        return ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
    elif status_code >= 400 and status_code < 500:
        return ConsumeEvent.BAD_ENTRY
    elif status_code >= 500 and status_code < 600:
        # Hmm. Could be server-side problem, or a bad entry.
        # We'll retry this service key a few times, and then decide that this
        # event is possibly a bad entry.
        return ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
    else:
        # anything 3xx and >= 5xx
        return ConsumeEvent.NOT_CONSUMED


def phone_home(guid, system_stats=None):
    # TODO finalize keys.
    phone_home_data = {
        "agent_id": guid,
        "agent_version": AGENT_VERSION,
        "agent_stats": pdQueue.get_status(throttle_info=True, aggregated=True)
    }
    if system_stats:
        phone_home_data['system_info'] = system_stats

    request = urllib2.Request(PHONE_HOME_URI)
    request.add_header("Content-type", "application/json")
    request.add_data(json.dumps(phone_home_data))
    try:
        response = httpswithverify.urlopen(request)
        result_str = response.read()
    except:
        main_logger.error("Error while phoning home:", exc_info=True)
        result_str = None

    if result_str:
        try:
            result = json.loads(result_str)
        except:
            main_logger.warning(
                "Error reading phone-home response data:",
                exc_info=True)
            result = {}

        # TODO store heartbeat frequency.
        result.get("heartbeat_frequency_sec")


def tick(sc, guid, system_stats=None):
    global main_logger

    # flush the event queue.
    main_logger.info("Flushing event queue")
    queue_processed = False
    try:
        pdQueue.flush(send_event)
        queue_processed = True
    except EmptyQueueError:
        main_logger.info("Nothing to do - queue is empty!")
    except IOError:
        main_logger.error("I/O error while flushing queue:", exc_info=True)
    except:
        main_logger.error("Error while flushing queue:", exc_info=True)

    # clean up if required.
    seconds_since_cleanup = int(time.time()) - Agent.lastCleanupTimeSec
    if seconds_since_cleanup >= mainConfig['cleanup_freq_sec']:
        try:
            pdQueue.cleanup(mainConfig['cleanup_before_sec'])
        except:
            main_logger.error("Error while cleaning up queue:", exc_info=True)
        Agent.lastCleanupTimeSec = int(time.time())

    # send phone home information if required.
    # TODO decide about threads for all these features.
    if queue_processed or system_stats:
        try:
            # phone home, sending out system info the first time.
            phone_home(guid, system_stats)
        except:
            main_logger.error("Error while phoning home:", exc_info=True)

    # schedule next tick.
    # note: system_stats is not required after first tick.
    sc.enter(mainConfig['check_freq_sec'], 1, tick, (sc, guid))


def _ensureWritableDirectories(make_missing_dir, *directories):
    problem_directories = []
    for directory in directories:
        if make_missing_dir and not os.path.exists(directory):
            try:
                os.mkdir(directory)
            except OSError:
                pass  # handled in the check immediately below
        if not os.access(directory, os.W_OK):
            problem_directories.append(directory)

    return problem_directories


# Override the generic daemon class to run our checks
class Agent(Daemon):

    lastCleanupTimeSec = 0

    def run(self):
        global log_dir, main_logger
        init_logging(log_dir)
        main_logger = logging.getLogger('main')

        main_logger.info('--')
        main_logger.info('pd-agent started')  # TODO: log agent version
        main_logger.info('--')

        main_logger.info('PID file: %s', self.pidfile)

        main_logger.debug('Collecting basic system stats')

        # Get some basic system stats to post back for development/testing
        import platform
        system_stats = {
            'machine': platform.machine(),
            'platform': sys.platform,
            'processor': platform.processor(),
            'python_version': platform.python_version()
            }

        if sys.platform == 'linux2':
            system_stats['platform_version'] = platform.dist()

        main_logger.info('System: ' + str(system_stats))

        guid = get_or_make_guid()
        main_logger.info('GUID: ' + guid)

        main_logger.debug('Creating tick instance')

        # Schedule the tick
        main_logger.info('check_freq_sec: %s', mainConfig['check_freq_sec'])
        s = sched.scheduler(time.time, time.sleep)
        tick(s, guid, system_stats)  # start immediately
        s.run()


# read persisted, valid GUID, or generate (and persist) one.
def get_or_make_guid():
    import uuid
    guid_file = os.path.join(
        agentConfig.get_conf_dirs()['data_dir'],
        "guid.txt")
    fd = None
    guid = None

    try:
        fd = open(guid_file, "r")
        guid = str(uuid.UUID(fd.readline().strip()))
    except IOError as e:
        import errno
        if e.errno != errno.ENOENT:
            main_logger.warning(
                'Could not read GUID from file %s' % guid_file,
                exc_info=True)
    except ValueError:
        main_logger.warning(
            'Invalid GUID in file %s' % guid_file,
            exc_info=True)
    finally:
        if fd:
            fd.close()

    if not guid:
        main_logger.info('Generating new GUID')
        guid = str(uuid.uuid4())
        fd = None
        try:
            fd = open(guid_file, "w")
            fd.write(guid)
        except IOError:
            main_logger.warning(
                'Could not write to GUID file %s' % guid_file,
                exc_info=True)
        finally:
            if fd:
                fd.close()
    return guid


def init_logging(log_dir):
    logFile = os.path.join(log_dir, 'pd-agent.log')
    # 10MB files
    handler = logging.handlers.RotatingFileHandler(
        logFile, maxBytes=10485760, backupCount=5
        )
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    handler.setFormatter(formatter)

    rootLogger = logging.getLogger()
    rootLogger.setLevel(mainConfig['log_level'])
    rootLogger.addHandler(handler)


# Control of daemon
if __name__ == '__main__':

    conf_dirs = agentConfig.get_conf_dirs()
    pidfile_dir = conf_dirs['pidfile_dir']
    log_dir = conf_dirs['log_dir']
    data_dir = conf_dirs['data_dir']
    outqueue_dir = conf_dirs["outqueue_dir"]
    db_dir = conf_dirs["db_dir"]

    problem_directories = _ensureWritableDirectories(
        agentConfig.is_dev_layout(),  # create directories in development
        pidfile_dir, log_dir, data_dir, outqueue_dir, db_dir
        )
    if problem_directories:
        messages = [
            "Directory %s: is not writable" % d
            for d in problem_directories
            ]
        messages.append('Agent may be running as the wrong user.')
        messages.append('Use: service pd-agent <command>')
        messages.append('Agent will now quit')
        raise SystemExit("\n".join(messages))

    from pdagent.thirdparty.argparse import ArgumentParser
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
        # FIXME: writeable test may only be needed for start
        raise SystemExit(
            'Unable to write the PID file at ' + pidFile + '\n' +
            'Agent will now quit'
            )

    # queue to work on.
    pdQueue = agentConfig.get_queue(dequeue_enabled=True)

    # Daemon instance from agent class
    daemon = Agent(pidFile)

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
        try:
            if _getDaemonPID():
                daemon.stop()
            os.remove(pidFile)
        except OSError:
            # Did not find pid file
            pass

    if 'start' == args.action:
        daemon.start()

    elif 'stop' == args.action:
        daemon.stop()

    elif 'restart' == args.action:
        daemon.restart()

    # XXX: unsafe - doesnt use pidfile, may want to log to stdout
    #elif 'foreground' == args.action:
    #    daemon.run()

    elif 'status' == args.action:
        pid = _getDaemonPID()
        if pid:
            print 'pd-agent is running as pid %s.' % pid
        else:
            print 'pd-agent is not running.'

    else:
        print 'Unknown command'
        sys.exit(1)

    sys.exit(0)
