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
import signal
import sys
import time


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
from pdagent.thirdparty.daemon import Daemon
from pdagent.phonehome import PhoneHomeThread
from pdagent.sendevent import SendEventThread


# Config handling
agentConfig = pdagent.config.load_agent_config()
mainConfig = agentConfig.get_main_config()


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


stop_signal = False


def _sig_term_handler(signum, frame):
    global stop_signal
    if not stop_signal:
        main_logger.info('Stopping due to signal #: %s' % signum)
        stop_signal = True


# Override the generic daemon class to run our checks
class Agent(Daemon):

    def run(self):
        global log_dir, main_logger
        init_logging(log_dir)
        main_logger = logging.getLogger('main')

        main_logger.info('*** pdagentd started')

        try:
            from pdagent.constants import AGENT_VERSION

            main_logger.info('PID file: %s', self.pidfile)

            main_logger.info('Agent version: %s', AGENT_VERSION)

            agent_id_file = os.path.join(
                agentConfig.get_conf_dirs()['data_dir'],
                "agent_id.txt")
            try:
                agent_id = get_or_make_agent_id(agent_id_file)
            except IOError:
                main_logger.fatal(
                    'Could not read from / write to agent ID file %s' %
                    agent_id_file,
                    exc_info=True
                )
                raise SystemExit
            except ValueError:
                main_logger.fatal(
                    'Invalid value in agent ID file %s' % agent_id_file,
                    exc_info=True
                )
                raise SystemExit
            main_logger.info('Agent ID: ' + agent_id)

            main_logger.debug('Collecting basic system stats')

            # Get some basic system stats to post back in phone-home
            import platform
            import socket
            system_stats = {
                'platform_name': sys.platform,
                'python_version': platform.python_version(),
                'host_name': socket.getfqdn()  # to show in stats-based alerts.
                # TODO ip address?
                }

            if sys.platform == 'linux2':
                system_stats['platform_version'] = platform.dist()

            main_logger.info('System: ' + str(system_stats))

            # Send event thread config
            check_freq_sec = mainConfig['check_freq_sec']
            send_event_timeout_sec = mainConfig['send_event_timeout_sec']
            cleanup_freq_sec = mainConfig['cleanup_freq_sec']
            cleanup_before_sec = mainConfig['cleanup_before_sec']

            start_ok = True
            send_thread = None
            phone_thread = None

            signal.signal(signal.SIGTERM, _sig_term_handler)

            try:
                send_thread = SendEventThread(
                    pdQueue, check_freq_sec,
                    send_event_timeout_sec,
                    cleanup_freq_sec, cleanup_before_sec
                    )
                send_thread.start()
            except:
                start_ok = False
                main_logger.error("Error starting send thread", exc_info=True)

            try:
                # we'll phone-home daily, although that will change if server
                # indicates a different frequency.
                heartbeat_frequency_sec = 60 * 60 * 24
                phone_thread = PhoneHomeThread(
                    heartbeat_frequency_sec,
                    pdQueue,
                    agent_id,
                    system_stats
                    )
                phone_thread.start()
            except:
                start_ok = False
                main_logger.error(
                    "Error starting phone home thread", exc_info=True
                    )

            try:
                if start_ok:
                    while not stop_signal:
                        time.sleep(1.0)
            except:
                main_logger.error("Error while sleeping", exc_info=True)

            try:
                if phone_thread:
                    phone_thread.stop_and_join()
            except:
                main_logger.error(
                    "Error stopping phone home thread", exc_info=True
                    )

            try:
                if send_thread:
                    send_thread.stop_and_join()
            except:
                main_logger.error("Error stopping send thread", exc_info=True)

        except SystemExit:
            main_logger.error('*** pdagentd exiting because of errors!')
            sys.exit(1)
        else:
            main_logger.info('*** pdagentd exiting normally!')
        sys.exit(0)


# read persisted, valid agent ID, or generate (and persist) one.
def get_or_make_agent_id(agent_id_file):
    import uuid
    fd = None
    agent_id = None

    try:
        fd = open(agent_id_file, "r")
        agent_id = str(uuid.UUID(fd.readline().strip()))
    except IOError as e:
        import errno
        if e.errno != errno.ENOENT:
            raise
    finally:
        if fd:
            fd.close()

    if not agent_id:
        main_logger.info('Generating new agent ID')
        agent_id = str(uuid.uuid4())
        fd = None
        try:
            fd = open(agent_id_file, "w")
            fd.write(agent_id)
        finally:
            if fd:
                fd.close()
    return agent_id


def init_logging(log_dir):
    logFile = os.path.join(log_dir, 'pd-agent.log')
    # 10MB files
    handler = logging.handlers.RotatingFileHandler(
        logFile, maxBytes=10485760, backupCount=5
        )
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(threadName)-20s %(name)-20s %(message)s"
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
