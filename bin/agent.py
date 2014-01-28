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
import sys
import signal
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
from pdagent.daemon import Daemon
from pdagent.sendevent import SendEventThread


# Config handling
agentConfig = pdagent.config.load_agent_config()
mainConfig = agentConfig.get_main_config()


def _ensureWritableDirectories(make_missing_dir, *directories):
    problemDirectories = []
    for directory in directories:
        if make_missing_dir and not os.path.exists(directory):
            try:
                os.mkdir(directory)
            except OSError:
                pass  # handled in the check immediately below
        if os.access(directory, os.W_OK) == False:
            problemDirectories.append(directory)

    return problemDirectories


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

        main_logger.warn('--- pdagentd started')
        # TODO: log pid, agent version

        main_logger.info('PID file: %s', self.pidfile)

        main_logger.debug('Collecting basic system stats')

        # Get some basic system stats to post back for development/testing
        import platform
        systemStats = {
            'machine': platform.machine(),
            'platform': sys.platform,
            'processor': platform.processor(),
            'python_version': platform.python_version()
            }

        if sys.platform == 'linux2':
            systemStats['platform_version'] = platform.dist()

        main_logger.info('System: ' + str(systemStats))

        # Send event thread
        check_freq_sec = mainConfig['check_freq_sec']
        cleanup_freq_sec = mainConfig['cleanup_freq_sec']
        cleanup_before_sec = mainConfig['cleanup_before_sec']

        send_thread = None

        signal.signal(signal.SIGTERM, _sig_term_handler)

        try:
            send_thread = SendEventThread(
                pdQueue, check_freq_sec,
                cleanup_freq_sec, cleanup_before_sec
                )
            send_thread.start()
        except:
            send_thread = None
            main_logger.error("Error starting send thread", exc_info=True)

        try:
            if send_thread:
                while not stop_signal:
                    time.sleep(1.0)
        except:
            main_logger.error("Error while sleeping", exc_info=True)

        try:
            if send_thread:
                send_thread.stop_and_join()
        except:
            main_logger.error("Error stopping send thread", exc_info=True)

        main_logger.warn('--- pdagentd exiting!')
        sys.exit(0)


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

    problemDirectories = _ensureWritableDirectories(
        agentConfig.is_dev_layout(),  # create directories in development
        pidfile_dir, log_dir, data_dir, outqueue_dir, db_dir
        )
    if problemDirectories:
        messages = [
            "Directory %s: is not writable" % d
            for d in problemDirectories
            ]
        messages.append('Agent may be running as the wrong user.')
        messages.append('Use: service pd-agent <command>')
        messages.append('Agent will now quit')
        raise SystemExit("\n".join(messages))

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
