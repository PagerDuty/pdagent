
"Generic Unix daemon class"

#
# Author:    www.boxedice.com
#
# http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
#
# License:   http://creativecommons.org/licenses/by-sa/3.0/
#
# Changes:
#
#    2013-2014 PagerDuty Inc
#        - See history at https://github.com/PagerDuty/agent/
#        - Based on the file at:
#            https://github.com/serverdensity/sd-agent/blob/master/daemon.py
#
# Previous Changes:
#
#    23rd Jan 2009 (David Mytton <david@boxedice.com>)
#        - Replaced hard coded '/dev/null in __init__ with os.devnull
#        - Added OS check to conditionally remove code that doesn't work on OS X
#        - Added output to console on completion
#        - Tidied up formatting
#    11th Mar 2009 (David Mytton <david@boxedice.com>)
#        - Fixed problem with daemon exiting on Python 2.4 (before SystemExit was part of the Exception base)
#    13th Aug 2010 (David Mytton <david@boxedice.com>
#        - Fixed unhandled exception if PID file is empty
#

# Core modules
import atexit
import os
import sys
import time

from signal import SIGTERM


class Daemon:
    """
    A generic daemon class.

    Usage: subclass the Daemon class and override the run() method
    """
    def __init__(
            self, pidfile,
            stdin=os.devnull, stdout=os.devnull, stderr=os.devnull
            ):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        """
        Do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """
        try:
            pid = os.fork()
            if pid > 0:
                # Exit from First parent
                _, status = os.waitpid(pid, 0)
                if status:
                    raise SystemExit("Error in second parent: %s" % status)
                else:
                    sys.exit(0)
        except OSError, e:
            raise SystemExit(
                "fork #1 failed: %d (%s)\n" % (e.errno, e.strerror)
                )

        # Decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # Do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Exit from second parent
                sys.exit(0)
        except OSError, e:
            raise SystemExit(
                "fork #2 failed: %d (%s)\n" % (e.errno, e.strerror)
                )

        if sys.platform != 'darwin':  # This block breaks on OS X
            # Redirect standard file descriptors
            sys.stdout.flush()
            sys.stderr.flush()
            si = file(self.stdin, 'r')
            so = file(self.stdout, 'a+')
            se = file(self.stderr, 'a+', 0)
            os.dup2(si.fileno(), sys.stdin.fileno())
            os.dup2(so.fileno(), sys.stdout.fileno())
            os.dup2(se.fileno(), sys.stderr.fileno())

        # Write pidfile
        atexit.register(self.delpid)  # Make sure pidfile is removed if we quit
        pid = str(os.getpid())
        file(self.pidfile, 'w+').write("%s\n" % pid)

    def delpid(self):
        os.remove(self.pidfile)

    def start(self):
        """
        Start the daemon
        """

        # Check for a pidfile to see if the daemon already runs
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        except SystemExit:
            pid = None

        if pid:
            message = "pidfile %s already exists. Is it already running?\n"
            raise SystemExit(message % self.pidfile)

        # Start the daemon
        self.daemonize()
        self.run()

    def run(self):
        """
        You should override this method when you subclass Daemon. It will be
        called after the process has been daemonized by start() or restart().
        """
