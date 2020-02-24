# TraceRobot plugin for PyTest

## What is it?

pytest-tracerobot is a Pytest plugin that records the execution trace of
test cases and outputs a Robot Framework compatible XML log file.

The generated XML log file can be converted into a human-friendly HTML log and
report files using 'rebot' tool from Robot Framework.

Tests do not need to be written differently to be tracerobot compatible.
Tracerobot understands what pytest is doing and acts accordingly.

## Current status

Current development status is Beta. It is being tested for production use.
I'm looking for volunteers to assist in development of TraceRobot and this  
plugin.

## Prerequisites

PyTest-TraceRobot needs Python 3, PyPi (pip3) and TraceRobot module (>=0.3.1).
TraceRobot module has a dependency to Robot Framework.
PyTest-TraceRobot has been tested with Python 3.6.8 and Robot Framework 3.1.1.

## Installation

First, download and install the TraceRobot module from
https://github.com/mrdegerholm/tracerobot.git

In the sources directory, run

sudo -H ./setup.py install

(This is going to be a PyPi package at some point, but we're not there yet).

Then, download and install the pytest-tracerobot from
https://github.com/mrdegerholm/pytest-tracerobot.git

In the sources directory, run

sudo -H ./setup.py install

This should also install the other dependencies if necessary.

## Running the example code

After installing the module, you can run the example code under the "example"
directory.

The example code comprises of a SUT (Software Under Test), and a few
test cases for that. The SUT is a very simple HTTP API stub.

To run the SUT, you will need to have Python "flask" module installed.
Flask is a REST API framework for Python. Use the following command to
install it:

`sudo -H pip3 install flask`

Run the SUT (Software Under testing) in one terminal:
`cd example`
`./gameserver.py`

Then, open an another terminal for running the tests:
`cd example`
`./run.sh`

This script runs both the tests and calls 'rebot' tool from Robot framework
to generate report.html and log.html from the generated output.xml.

If all goes well, you can use your favorite browser to open the report
and/or log documents.

About the sample tests:
  - testgameserver.py has a few simple test cases testing the actual
    gameserver SUT.
  - math.py is an example that illustrates how easy it can be to write
    tests with pytest and pytest-tracerobot at the minimum.

## Writing test suites, test cases and keywords

Basic rule is that you don't need to do any tracerobot specific changes
to your test code. Just write your tests as you would do normally with
pytest.

Based on Robot Framework testing model, Pytset-TraceRobot internally
uses the following concepts:

  1. Suite: a collection of tests. There can be one or multiple suites per
     test run. Suites can be nested.
     Suites can have setup and teardown related keywords.
     In pytest-tracerobot, suite-level setup/teardown can be implemented using
     one or more class/module/session-scoped fixture functions
     (refer to PyTest documentation for more information).
  2. Test case: a single test case. Test cases cannot be nested.
     Test cases can have setup and teardown related keywords.
     In pytest-tracerobot, test-level setup/teardown can be implemented using
     one or more function-scoped fixture functions
     (refer to PyTest documentation for more information).
  3. Keyword: basically any Python function used by a test case. Keywords can
     call other keywords.
  4. Messages: arbitrary log messages can be inserted into log files.

Pytest-tracerobot uses the pytest collections and python tracer module to
automatically map the test execution into the suite/test case/
keyword level objects and write them into the XML log file.

## Autotracing scope

Automatic execution tracing is enabled in the python files within current
working directory tree. By default, private methods (those starting with an
underscore) are not logged, but this can be changed with --autotrace-privates
option to pytest. Test libraries that should be traced can be added with
--autotrace-libpaths option to pytest.

## Logging of assert statements

In order to get all the asserts logged, you must have the following contents in
your pytest.ini file:

    [pytest]
    enable_assertion_pass_hook=true

Please note: if you already ran some tests without that setting, you may need
to remove the .pyc files from your test project. This is because pytest will
need to instrument the test code differently with this setting enabled.

## Python log facility

While under a test case, any log message written with python logging facility
will be written to the XML log file as well.

## Marks / Tags

In PyTest, each test can be decorated using
`pytest.mark.MARK` where MARK can be freely chosen. Then, when running tests,
you can select to run only tests with specific mark(s) using "-m MARK"
command line option (on command line MARK is actually a regexp so this is quite
flexible).

In newer versions of pytest, custom marks should be described in pytest.ini file
to avoid warnings.

In Robot Framework output, marks are converted to tags.

## Docstrings

Python docstrings for test and keyword functions get logged within Robot log
as documentation for those tets/keywords.

## Acknowledgements

Specials thanks go to Ossi Rajuvaara and Mica Nyholm for contributing,
feedback and ideas.

I'm also thankful to Robot Framework and PyTest community for producing such
high-quality open-source products.
