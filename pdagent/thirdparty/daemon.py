"Unix process daemonization"

#
# Copyright (c) 2013-2014, PagerDuty, Inc. and other authors
#
# License:   http://creativecommons.org/licenses/by-sa/3.0/
#
# Changes:
# - See https://github.com/PagerDuty/agent/ for changes by PagerDuty, Inc.
# - Based on https://github.com/serverdensity/sd-agent/blob/master/daemon.py
#
# Original based on the article at:
#   http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
#
# See Stevens' "Advanced Programming in the UNIX Environment" (ISBN 0201563177)
# for details about double-forking.
#

import atexit
import os
import sys
import subprocess

def daemonize(
        pidfile,
        stdin=os.devnull, stdout=os.devnull, stderr=os.devnull,
        umask=0  # default double-fork recommended umask for daemonize
        ):
    """
    Do the UNIX double-fork magic.

    In the original process and the first child, this method will always throw
    SystemExit (directly or via sys.exit) with an appropriate exit status.

    On success, it will return normally in the daemonized grand-child process.
    """
    # Check for a pidfile to see if the daemon already runs
    try:
        pf = open(pidfile, 'r')
        pid = int(pf.read().strip())
        pf.close()
    except (IOError, ValueError):
        pid = None

    if (pid and _pid_exists(pid)):
        message = "pidfile %s already exists and the process is running!\n"
        raise SystemExit(message % pidfile)
    if pid:
        os.remove(pidfile)

    # Do first fork
    try:
        pid = os.fork()
        if pid > 0:
            # Exit from First parent
            _, status = os.waitpid(pid, 0)
            if status:
                raise SystemExit("Error in second parent: %s" % status)
            else:
                sys.exit(0)
    except OSError as e:
        raise SystemExit("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))

    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(umask)

    # Do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # Exit from second parent
            sys.exit(0)
    except OSError as e:
        raise SystemExit("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))

    if sys.platform != 'darwin':  # This block breaks on OS X
        _redirect_std_file_descriptors(stdin, stdout, stderr)

    # Make sure pidfile is removed if we quit
    def delpid():
        os.remove(pidfile)
    atexit.register(delpid)

    # Write pidfile
    pid = str(os.getpid())
    open(pidfile, 'w+').write("%s\n" % pid)


def _redirect_std_file_descriptors(stdin, stdout, stderr):
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    si = open(stdin, 'r')
    so = open(stdout, 'a+')
    se = open(stderr, 'a+')
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

def _pid_exists(pid):
    cmd = "/bin/ps %s" % pid
    child = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    child.communicate()[0]
    return child.returncode < 1
