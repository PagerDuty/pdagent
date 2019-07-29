# SCons Setup

SCons 2.3.x setup notes for OS X 10.8 (Mountain Lion).

Note that some test-related commands in this build file run on virtual
machines, and assume that Vagrant has been installed on this machine.
(See the included setup instructions for Vagrant.)


## Installation

* Download the scons gzip tar file (or zip file) for the 2.3.x version from
  https://sourceforge.net/projects/scons/files/scons/2.3.6/scons-2.3.6.tar.gz/download
* Extract it to any location.
* Go to the scons-2.3.x directory in the extracted location, and run
  `python setup.py install`
  to install scons in the system directories.
* You can check the version of your scons installation by running
  `scons -v`


## Using SCons

* Run `scons -h|--help` to see help information for the current project.
* Run `scons` to execute the default target for the current project.
* If you are interested, run `scons -H` to see help on options supported
  by scons.
