#
# Build script for agent.
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

import os
import subprocess
import sys


_PACKAGE_TYPES = ["deb", "rpm"]
_DEB_BUILD_VM = "agent-minimal-ubuntu1204"
_RPM_BUILD_VM = "agent-minimal-centos65"


def create_repo(target, source, env):
    """Create installable local repository for supported operating systems."""
    gpg_home = env.get("gpg_home")
    if not gpg_home:
        print (
            "No gpg-home was provided!\n" +
            "If required, run this command to create a new gpg-home:\n" +
            "gpg --homedir=/desired/path --gen-key"
            )
        return 1
    else:
        gpg_home = gpg_home[0]

    env.Execute(Mkdir(tmp_dir))
    env.Execute(Mkdir(target_dir))

    # copy gpg-home to VM-accessible location.
    if subprocess.call(["cp", "-r", gpg_home, tmp_dir]):
        print "Cannot copy %s to %s" % (gpg_home, tmp_dir)
        return 1
    else:
        # ... and /vagrant-ify the new gpg-home path.
        remote_gpg_home = os.path.join(
            remote_project_root,
            tmp_dir,
            os.path.basename(gpg_home)
            )

    virts = env.get("virts")
    remote_target_dir = os.path.join(remote_project_root, target_dir)
    ret_code = 0

    if virts is None or [v for v in virts if v.find("ubuntu") != -1]:
        ret_code += _create_repo(
            _DEB_BUILD_VM,
            "deb",
            remote_gpg_home,
            remote_target_dir
            )

    if virts is None or [v for v in virts if v.find("centos") != -1]:
        ret_code += _create_repo(
            _RPM_BUILD_VM,
            "rpm",
            remote_gpg_home,
            remote_target_dir
            )

    if not ret_code:
        # export public key into a temporary location to help installation.
        export_cmd = ["gpg", "--homedir", gpg_home, "--export", "--armor"]
        fd = open(os.path.join(tmp_dir, "GPG-KEY-pagerduty"), "w")
        fd.writelines(subprocess.check_output(export_cmd))
        fd.close()

    return ret_code


def run_integration_tests(target, source, env):
    """Run integration tests on running virts."""
    source_paths = [s.path for s in source]
    pre_cmds = []
    prev_ver = env.get("upgrade_from")
    if (prev_ver):
        pre_cmds.append("export UPGRADE_FROM_VERSION=%s" % prev_ver[0])
    test_runner_file = _generate_remote_test_runner_file(
        source_paths,
        lambda f: f.startswith("test_") and f.endswith(".sh"),
        executable="sh",
        pre_cmds=pre_cmds)
    return _run_on_virts("sh %s" % test_runner_file, env.get("virts"))


def run_unit_tests(target, source, env):
    """Run unit tests on specific / all running virts."""
    source_paths = [s.path for s in source]
    remote_test_runner = os.path.join(remote_project_root, "run-tests.py")
    test_paths = _get_file_paths_recursive(
            source_paths,
            lambda f: f.startswith("test_") and f.endswith(".py"))
    test_paths.sort()
    remote_test_command = ["python", remote_test_runner]
    remote_test_command.extend(
        [os.path.join(remote_project_root, t) for t in test_paths])
    return _run_on_virts(" ".join(remote_test_command), env.get("virts"))


def run_unit_tests_local(target, source, env):
    """Run unit tests on current machine."""
    source_paths = [s.path for s in source]
    test_paths = _get_file_paths_recursive(
        source_paths,
        lambda f: f.startswith("test_") and f.endswith(".py"))
    test_paths.sort()
    test_command = [sys.executable, "run-tests.py"]
    test_command.extend(test_paths)
    return subprocess.call(test_command)


def start_virtual_boxes(target, source, env):
    virts = env.get("virts")
    if not virts:
        virts =  _get_minimal_virt_names()
    start_cmd = ["vagrant", "up"]
    start_cmd.extend(virts)
    return subprocess.call(start_cmd)


def destroy_virtual_boxes(target, source, env):
    virts = env.get("virts")
    force = env.get("force")
    if force:
        force = force.lower() in ['true', 'yes', 'y', '1']
    if not virts:
        virts = _get_minimal_virt_names()
    destroy_cmd = ["vagrant", "destroy"]
    if not force:
        msg = "You must manually confirm deletion of VMs."
        h_border = "-" * len(msg)
        print h_border
        print msg
        print h_border
    else:
        destroy_cmd.append("-f")
    destroy_cmd.extend(virts)
    return subprocess.call(destroy_cmd)


def sync_from_remote_repo(target, source, env):
    repo_root = _pre_sync_checks(env)
    if not repo_root:
        return 1

    env.Execute(Mkdir(target_dir))
    for pkg_type in _PACKAGE_TYPES:
        pkg_root = os.path.join(target_dir, pkg_type)
        if not os.path.isdir(pkg_root):
            env.Execute(Mkdir(pkg_root))

    if repo_root.startswith("s3://"):
        return _sync_s3_package_repo(repo_root, target_dir, outbound=False)


def sync_to_remote_repo(target, source, env):
    repo_root = _pre_sync_checks(env)
    if not repo_root:
        return 1

    for pkg_type in _PACKAGE_TYPES:
        pkg_root = os.path.join(target_dir, pkg_type)
        if not (os.path.isdir(pkg_root) and os.listdir(pkg_root)):
            print "No content to sync from: %s" % pkg_root
            print "Sync-to-remote was NOT STARTED."
            return 1

    pkg_types_str = "{%s}" % ",".join(_PACKAGE_TYPES)
    print "This will copy <project_root>/%s/%s to %s/%s" % \
        (target_dir, pkg_types_str, repo_root, pkg_types_str)
    print "All existing content in %s/%s will remain as is." % \
        (repo_root, pkg_types_str)
    if raw_input("Are you sure? [y/N] ").lower() not in ["y", "yes"]:
        return 1

    if repo_root.startswith("s3://"):
        return _sync_s3_package_repo(repo_root, target_dir, outbound=True)


def _create_repo(virt, virt_type, gpg_home, local_repo_root):
    # Assuming that all requisite packages are available on virt.
    # (see build-linux/howto.txt)
    print "\nCreating local %s repository..." % virt_type
    make_file = os.path.join(
        remote_project_root,
        build_linux_dir,
        "make_%s.sh" % virt_type)
    return _run_on_virts(
        "sh %s %s %s" % (make_file, gpg_home, local_repo_root),
        [virt]
        )


def _pre_sync_checks(env):
    repo_root = env.get("repo_root")
    if not repo_root:
        print "No repo-root was provided!"
        return None
    else:
        repo_root = repo_root[0]

    if repo_root.startswith("s3://"):
        if subprocess.call(["which", "s3cmd"]):
            print "No s3cmd found!\nInstall from http://s3tools.org/download"
            return None
    else:
        print "Unrecognized remote repository type for location: " + repo_root
        return None

    return repo_root


def _sync_s3_package_repo(
        s3_root,
        local_root,
        pkg_types=_PACKAGE_TYPES,
        outbound=False
        ):
    r = 0
    for pkg_type in pkg_types:
        # note that both src and dest locations need to end with '/'
        if outbound:
            src = os.path.join(local_root, pkg_type, "")
            dest = "%s/%s/" % (s3_root, pkg_type)
        else:
            src = "%s/%s/" % (s3_root, pkg_type)
            dest = os.path.join(local_root, pkg_type, "")
        print "Syncing %s -> %s..." % (src, dest)
        r += subprocess.call(["s3cmd", "sync", src, dest])
    return r


def _generate_remote_test_runner_file(
    source_paths,
    test_filename_matcher,
    executable=sys.executable,
    pre_cmds=None):

    env.Execute(Mkdir(tmp_dir))
    test_runner_file = os.path.join(tmp_dir, "run_tests")

    test_files = _get_file_paths_recursive(source_paths, test_filename_matcher)
    test_files.sort()
    # these are under the remote project root dir on virtual boxes
    test_run_paths = [os.path.join(remote_project_root, t) for t in test_files]

    run_commands = ["aggr_e=0"]
    if pre_cmds:
        run_commands.extend(pre_cmds)
    for test in test_run_paths:
        # using printf because sh's echo in ubuntu1004 does not support
        # interpreting backslash escapes.
        run_commands.append("printf '\\n=== %s\\n' " + test)
        run_commands.append(" ".join([executable, test]))
        run_commands.append("e=$?")
        run_commands.append("printf '=== Exited with %d\\n' $e")
        run_commands.append("aggr_e=$(( $aggr_e + $e ))")
    run_commands.append("exit $aggr_e")

    _create_text_file(test_runner_file, run_commands)

    return os.path.join(remote_project_root, test_runner_file)


def _get_file_paths_recursive(source_paths, filename_matcher):
    dirs_traversed = set()
    files = set()

    def _add_files(dir_path):
        dirs_traversed.add(dir_path)
        for dirname, subdirnames, filenames in os.walk(dir_path):
            for subdir in subdirnames:
                dirs_traversed.add(os.path.join(dirname, subdir))
            for filename in filenames:
                if filename_matcher(filename):
                    files.add(os.path.join(dirname, filename))

    for src in source_paths:
        if os.path.isdir(src):
            if not src in dirs_traversed:
                _add_files(src)
        else:
            if filename_matcher(os.path.basename(src)):
                files.add(src)
    return list(files)


def _create_text_file(filepath, data):
    out = open(filepath, "w")
    out.write(os.linesep.join(data))
    out.close()


def _get_arg_values(key, default=None):
    values = [v for k, v in ARGLIST if k == key]
    if not values:
        values = default
    return values


def _get_minimal_virt_names(running=False):
    return [
        v.split()[0] for v in
        subprocess
        .check_output(["vagrant", "status"])
        .splitlines()
        if v.startswith("agent-minimal-") and
        (not running or v.find(" running (") >= 0)
    ]


def _run_on_virts(remote_command, virts=None):
    exit_code = 0
    if not virts:
        virts = _get_minimal_virt_names(running=True)
    for virt in virts:
        command = ["vagrant", "ssh", virt, "-c", remote_command]
        print "Running %s" % command
        exit_code += subprocess.call(command)
    return exit_code


env = Environment()

env.Help("""
Usage: scons [command [command...]]
where supported commands are:
build                   Runs unit tests on virtual machines, creates local
                        repos and then runs integration tests on virtual
                        machines.
                        This is the default command if none is specified.
--clean|-c              Removes generated artifacts.
destroy-virt            Destroy the given virtual machine (provided using the
                        `virt` option), or all 'minimal' virtual machines (ones
                        with names containing 'minimal' in them.)
publish                 Uploads local repository contents for agent into
                        remote repository.
                        Also, the required arguments for 'local-repo' and
                        'sync-from-remote-repo' need to be passed in.
local-repo              Creates installable local repository for supported OS
                        distributions.
                        You will need to pass a gpg-home argument for this,
                        where gpg-home contains the key rings to sign the
                        Agent packages with. You could run this command to
                        generate required content:
                        gpg --homedir=/desired/path --gen-key
start-virt              Start the given virtual machine (provided using the
                        `virt` option), or all 'minimal' virtual machines (ones
                        with names containing 'minimal' in them.)
sync-from-remote-repo   Downloads already-published package hierarchy from the
                        given remote repository. Required if the repository is
                        to be updated with new / modified package.
                        You will need to pass a repo-root argument for this,
                        which is the location of remote repository. Location
                        types supported, and corresponding syntax:
                        S3: s3://<bucket>[/<path>]  <--requires `s3cmd`.
sync-to-remote-repo     Uploads already-published packages from the given
                        remote repository. Required if the repository is to be
                        updated with new / modified package.
                        You will need to pass a repo-root argument for this.
                        Refer 'sync-from-remote-repo'.
test                    Runs unit tests on specific virtual machines, bringing
                        the virtual machine up if required.
                        By default, runs on all virtual machines. Specific
                        virtual machines can be provided using the `virt`
                        option, multiple times if required.
                        By default, runs all tests in `pdagenttest` recursively.
                        (Test files should be named in the format `test_*.py`.)
                        Specific unit tests can be run by providing them as
                        arguments to the `test` option, multiple times if
                        required. Both test files and test directories are
                        supported.
                        e.g.
                        scons test test=pdagenttest/test_foo.py \\
                                   virt=agent-minimal-centos
test-integration        Runs integration tests on specific virtual machines,
                        bringing the virtual machine up if required.
                        By default, runs on all virtual machines. Specific
                        virtual machines can be provided using the `virt`
                        option, multiple times if required.
                        By default, runs all tests in `pdagenttestinteg`
                        recursively. (Test files should be named in the format
                        `test_*.sh`.) Specific tests can be run by providing
                        them as arguments to the `test` option, multiple times
                        if required. Both test files and test directories are
                        supported.
                        e.g.
                        scons test-integration \\
                            test=pdagenttestinteg/test_foo.sh \\
                            virt=agent-minimal-centos
                        If you want your tests to install a previous version
                        of the agent, upgrade it to this version, and then run
                        integration tests on the upgraded version, provide the
                        upgrade-from option. (e.g. upgrade-from=1.0)
test-local              Runs unit tests on the local machine.
                        Please see 'test' command for more details about using
                        `test` option to run specific unit tests.
""")

build_linux_dir = "build-linux"
build_linux_target_dir = os.path.join(build_linux_dir, "target")
target_dir = "target"
tmp_dir = os.path.join(target_dir, "tmp")
remote_project_root = os.sep + "vagrant"

unit_test_local_task = env.Command(
    "test-local",
    _get_arg_values("test", ["pdagenttest"]),
    env.Action(run_unit_tests_local, "\n--- Running unit tests locally")
    )

start_virts_task = env.Command(
    "start-virt",
    None,
    env.Action(start_virtual_boxes, "\n--- Starting virtual boxes"),
    virts=_get_arg_values("virt")
    )

destroy_virts_task = env.Command(
    "destroy-virt",
    None,
    env.Action(destroy_virtual_boxes, "\n--- Destroying virtual boxes"),
    virts=_get_arg_values("virt"),
    force=_get_arg_values("force-destroy")  # e.g. force-destroy=true
    )

unit_test_task = env.Command(
    "test",
    _get_arg_values("test", ["pdagenttest"]),
    env.Action(run_unit_tests, "\n--- Running unit tests on virtual boxes"),
    virts=_get_arg_values("virt")
    )
env.Requires(unit_test_task, start_virts_task)

create_repo_task = env.Command(
    "local-repo",
    None,
    env.Action(create_repo, "\n--- Creating installable local repository"),
    virts=_get_arg_values("virt"),
    gpg_home=_get_arg_values("gpg-home")
    )
env.Requires(create_repo_task, [unit_test_task, start_virts_task])

integration_test_task = env.Command(
    "test-integration",
    _get_arg_values("test", ["pdagenttestinteg"]),
    env.Action(
        run_integration_tests,
        "\n--- Running integration tests on virtual boxes"
        ),
    virts=_get_arg_values("virt"),
    upgrade_from=_get_arg_values("upgrade-from")
    )
env.Requires(integration_test_task, [start_virts_task])

sync_from_remote_repo_task = env.Command(
    "sync-from-remote-repo",
    None,
    env.Action(
        sync_from_remote_repo,
        "\n--- Syncing packages from remote package repository"
        ),
    repo_root=_get_arg_values("repo-root")
    )

sync_to_remote_repo_task = env.Command(
    "sync-to-remote-repo",
    None,
    env.Action(
        sync_to_remote_repo,
        "\n--- Syncing packages to remote package repository"
        ),
    repo_root=_get_arg_values("repo-root")
    )

# specify directories to be cleaned up for various targets
env.Clean([unit_test_task, integration_test_task], tmp_dir)
env.Clean([create_repo_task], target_dir)

build_task = env.Alias(
    "build",
    [unit_test_task, create_repo_task, integration_test_task]
    )
publish_task = env.Alias(
    "publish",
    [
    destroy_virts_task,
    sync_from_remote_repo_task,
    create_repo_task,
    integration_test_task,
    sync_to_remote_repo_task
    ]
    )

# task to run if no command is specified.
if env.GetOption("clean"):
    # workaround to get 'clean' to clean everything, and
    # not just the output of the usual default target.
    env.Default(".")
else:
    env.Default(build_task)
