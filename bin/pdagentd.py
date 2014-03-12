#!/usr/bin/python
#
# PagerDuty Agent daemon.
# See https://github.com/PagerDuty/agent for details.
#
# Copyright (c) 2013-2014, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the copyright holder nor the
#     names of its contributors may be used to endorse or promote products
#     derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#


# standard python modules
import logging.handlers
import os
import platform
import signal
import socket
import sys
import time
import uuid


# Check we're running as main
if __name__ != '__main__':
    raise SystemExit(
        "This module must be run as main.\n" +
        "Agent will now quit"
        )

# Check Python version.
if sys.version_info[0:2] not in ((2, 6), (2, 7)):
    raise SystemExit(
        "Agent requires Python version 2.6 or 2.7.\n" +
        "Agent will now quit"
        )

# Check we're not running as root
if os.geteuid() == 0:
    raise SystemExit(
        "Agent should not be run as root. Use: sudo service pdagent <command>\n" +
        "Agent will now quit"
        )

# Load config
try:
    import pdagent.config
except ImportError:
    # Fix up for dev layout
    import sys
    from os.path import realpath, dirname
    sys.path.append(dirname(dirname(realpath(__file__))))
    import pdagent.config


# Process config
# Be careful about what we do here! The daemonization double-fork has not
# happened yet! For example, os.getpid() cached here will be "wrong" later!
agent_config = pdagent.config.load_agent_config()
main_config = agent_config.get_main_config()

conf_dirs = agent_config.get_conf_dirs()
pidfile_dir = conf_dirs['pidfile_dir']
log_dir = conf_dirs['log_dir']
data_dir = conf_dirs['data_dir']
outqueue_dir = conf_dirs["outqueue_dir"]
db_dir = conf_dirs["db_dir"]

agent_id_file = agent_config.get_agent_id_file()

pidfile = os.path.join(pidfile_dir, 'pdagentd.pid')

pd_queue = agent_config.get_queue(dequeue_enabled=True)


# Check directories
def _ensure_writable_directories(make_missing_dir, *directories):
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


def _check_dirs():
    problem_directories = _ensure_writable_directories(
        agent_config.is_dev_layout(),  # create directories in development
        pidfile_dir, log_dir, data_dir, outqueue_dir, db_dir
        )
    if problem_directories:
        messages = [
            "Directory %s: is not writable" % d
            for d in problem_directories
            ]
        messages.append('Agent may be running as the wrong user.')
        messages.append('Use: sudo service pdagent <command>')
        messages.append('Agent will now quit')
        raise SystemExit("\n".join(messages))

    if not os.access(pidfile_dir, os.W_OK):
        raise SystemExit(
            'No write-access to PID file directory ' + pidfile_dir + '\n' +
            'Agent will now quit'
            )

_check_dirs()


# Import agent modules
from pdagent.constants import AGENT_VERSION
from pdagent.thirdparty.daemon import daemonize
from pdagent.pdthread import RepeatingTaskThread
from pdagent.heartbeat import HeartbeatTask
from pdagent.phonehome import PhoneHomeTask
from pdagent.sendevent import SendEventTask


# ---- The following functions run after daemonization.
# ---- This means they must use logging & not stdout/stderr.

# Non-config globals
stop_signal = False
main_logger = None
agent_id = None
system_stats = None
task_threads = None


def _sig_term_handler(signum, frame):
    global stop_signal
    if not stop_signal:
        main_logger.info('Stopping due to signal #: %s' % signum)
        stop_signal = True


def make_sendevent_task():
    # Send event thread config
    send_interval_secs = main_config['send_interval_secs']
    cleanup_interval_secs = main_config['cleanup_interval_secs']
    cleanup_threshold_secs = main_config['cleanup_threshold_secs']
    return SendEventTask(
        pd_queue,
        send_interval_secs,
        cleanup_interval_secs,
        cleanup_threshold_secs
        )


def make_phonehome_task():
    # by default, phone-home daily
    phonehome_interval_secs = 60 * 60 * 24
    return PhoneHomeTask(
        phonehome_interval_secs,
        pd_queue,
        agent_id,
        system_stats
        )


def make_heartbeat_task():
    # by default, heartbeat every hour
    heartbeat_interval_secs = 60 * 60
    return HeartbeatTask(heartbeat_interval_secs, agent_id)


def make_agent_tasks():
    mk_tasks = [
        make_sendevent_task,
        make_phonehome_task,
        make_heartbeat_task,
        ]
    return [mk_task() for mk_task in mk_tasks]


def create_and_start_task_threads(tasks):
    global task_threads
    task_threads = []
    for task in tasks:
        try:
            rtthread = RepeatingTaskThread(task)
            rtthread.setDaemon(True)  # don't let thread block exit
            rtthread.start()
            task_threads.append(rtthread)
        except:
            main_logger.fatal(
                "Error starting thread for task %s" % task.get_name(),
                exc_info=True
                )
            return False
    return True


def stop_task_threads():
    global task_threads
    for rtthread in task_threads:
        try:
            rtthread.stop_and_join()
        except:
            main_logger.error(
                "Error stopping thread %s:" % rtthread, exc_info=True
                )
    task_threads = None


def run():
    global main_logger, agent_id, system_stats
    pid = os.getpid()
    init_logging(log_dir)
    main_logger = logging.getLogger('main')
    main_logger.info("*** pdagentd starting! pid=%s" % pid)

    all_ok = True
    try:
        main_logger.info('PID file: %s', pidfile)
        main_logger.info('Agent version: %s', AGENT_VERSION)

        # Load/create agent id
        agent_id = get_or_make_agent_id()
        main_logger.info('Agent ID: ' + agent_id)

        # Dump main config
        main_logger.debug("Main Config: %s" % main_config)

        # Get some basic system stats to post back in phone-home
        main_logger.debug('Collecting basic system stats')
        system_stats = {
            'platform_name': sys.platform,
            'python_version': platform.python_version(),
            'host_name': socket.getfqdn()  # to show in stats-based alerts.
            }
        if sys.platform == 'linux2':
            system_stats['platform_version'] = platform.dist()
        main_logger.info('System: ' + str(system_stats))

        # Configure SIGTERM handler
        main_logger.debug("Setting signal handler for SIGTERM")
        signal.signal(signal.SIGTERM, _sig_term_handler)

        # Set default socket timeout
        default_socket_timeout = 10
        main_logger.debug(
            "Setting default socket timeout to %d" % default_socket_timeout
            )
        socket.setdefaulttimeout(default_socket_timeout)

        # Create tasks and task runner threads
        tasks = make_agent_tasks()
        all_ok = create_and_start_task_threads(tasks)

        # Sleep till it's time to exit
        if all_ok:
            try:
                main_logger.debug(
                    "Main thread sleeping till we need to stop!"
                    )
                while all_ok and not stop_signal:
                    time.sleep(1.0)
                    for rtthread in task_threads:
                        if not rtthread.is_alive():
                            main_logger.fatal(
                                "Thread %s is not alive!" % rtthread
                                )
                            all_ok = False
            except:
                main_logger.fatal("Error while sleeping", exc_info=True)
                all_ok = False

        # Stop task runner threads
        stop_task_threads()

    except SystemExit:
        all_ok = False
    except:
        all_ok = False
        main_logger.error("Uncaught error:", exc_info=True)

    # Exit
    if all_ok:
        main_logger.info("*** pdagentd exiting normally! pid=%s" % pid)
        sys.exit(0)
    else:
        main_logger.error(
            "*** pdagentd exiting due to fatal errors! pid=%s" % pid
            )
        sys.exit(1)


# read persisted, valid agent ID, or generate (and persist) one.
def get_or_make_agent_id():
    try:
        # try to load existing agent id
        if os.path.exists(agent_id_file):
            fd = None
            try:
                fd = open(agent_id_file, "r")
                return str(uuid.UUID(fd.readline().strip()))
            finally:
                if fd:
                    fd.close()

        # no agent id persisted yet.
        main_logger.info('Generating new agent ID')
        agent_id = str(uuid.uuid4())
        fd = None
        try:
            fd = open(agent_id_file, "w")
            fd.write(agent_id)
            fd.write('\n')
        finally:
            if fd:
                fd.close()
        return agent_id
    except IOError:
        main_logger.fatal(
            'Could not read from / write to agent ID file %s' % agent_id_file,
            exc_info=True
            )
        raise SystemExit
    except ValueError:
        main_logger.fatal(
            'Invalid value in agent ID file %s' % agent_id_file,
            exc_info=True
            )
        raise SystemExit


def init_logging(log_dir):
    log_file = os.path.join(log_dir, 'pdagentd.log')
    # 10MB files
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10485760, backupCount=5
        )
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(threadName)-20s %(name)-20s %(message)s"
        )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(main_config['log_level'])
    root_logger.addHandler(handler)


# ---- Daemonize and run agent

daemonize(pidfile, zero_umask=False)
run()
