#!/usr/bin/env python
from sandbox import HAVE_CSANDBOX
from sys import version_info
from sandbox.test import SkipTest, createSandboxConfig
from sandbox.test.tools import getTests
from sandbox.version import VERSION

def parseOptions():
    from optparse import OptionParser

    parser = OptionParser(usage="%prog [options]")
    parser.add_option("--raise",
        help="Don't catch exception",
        dest="raise_exception",
        action="store_true")
    parser.add_option("--debug",
        help="Enable debug mode (enable stdout and stderr features)",
        action="store_true")
    parser.add_option("-k", "--keyword",
        help="Only execute tests with name containing KEYWORD",
        type='str')
    options, argv = parser.parse_args()
    if argv:
        parser.print_help()
        exit(1)
    return options

def run_tests(options, use_subprocess, cpython_restricted, persistent_child):
    print((
        "Run tests with cpython_restricted=%s, use_subprocess=%s "
        "and persistent_child=%s") % (
        cpython_restricted, use_subprocess, persistent_child))
    print("")
    createSandboxConfig.cpython_restricted = cpython_restricted
    createSandboxConfig.use_subprocess = use_subprocess
    createSandboxConfig.persistent_child = persistent_child

    # Get all tests
    all_tests = getTests(globals(), options.keyword)

    # Run tests
    nerror = 0
    nskipped = 0
    if version_info < (2, 6):
        base_exception = Exception
    else:
        base_exception = BaseException
    for func in all_tests:
        name = '%s.%s()' % (func.__module__.split('.')[-1], func.__name__)
        if options.debug:
            print(name)
        try:
            func()
        except SkipTest, skip:
            print("%s: skipped (%s)" % (name, skip))
            nskipped += 1
        except base_exception, err:
            nerror += 1
            print("%s: FAILED! %r" % (name, err))
            if options.raise_exception:
                raise
        else:
            print "%s: ok" % name
    print("")
    return nskipped, nerror, len(all_tests)

def main():
    options = parseOptions()
    createSandboxConfig.debug = options.debug

    print("Run the test suite on pysandbox %s with Python %s.%s"
          % (VERSION, version_info[0], version_info[1]))
    if not HAVE_CSANDBOX:
        print("WARNING: _sandbox module is missing")
    print

    nskipped, nerrors, ntests = 0, 0, 0
    for use_subprocess in (False, True):
        for persistent_child in (False, True):
            for cpython_restricted in (False, True):
                result = run_tests(options, use_subprocess,
                                   cpython_restricted, persistent_child)
                nskipped += result[0]
                nerrors += result[1]
                ntests += result[2]
                if options.raise_exception and nerrors:
                    break

    # Exit
    from sys import exit
    if nerrors:
        print("%s ERRORS!" % nerrors)
        exit(1)
    else:
        print("%s tests succeed (%s skipped)" % (ntests, nskipped))
        exit(0)

if __name__ == "__main__":
    main()

