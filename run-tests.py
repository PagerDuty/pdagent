
import os, subprocess, sys


def runtests(test_files):
    total = 0
    errs = 0
    test_env = os.environ.copy()
    test_env["PYTHONPATH"] = \
        test_env.get("PYTHONPATH", "") + os.pathsep + os.getcwd()
    for test_file in test_files:
        print >> sys.stderr, "FILE:", test_file
        exit_code = subprocess.call([sys.executable, test_file], env=test_env)
        total += 1
        errs += (exit_code != 0)
    print >> sys.stderr, "SUMMARY: %s total / %s error (%s)" \
        % (total, errs, sys.executable)
    return errs


if __name__ == "__main__":
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    sys.exit(runtests(sys.argv[1:]))
