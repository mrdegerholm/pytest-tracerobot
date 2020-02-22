import os
import traceback
import tracerobot
import logging
import pytest
import _pytest

# Set to True to enable trace log of some hook calls to stdout
HOOK_DEBUG = False

def common_items(iter1, iter2):
    common = []
    for first, second in zip(iter1, iter2):
        if first != second:
            break
        common.append(first)
    return common

class TraceRobotPythonLogger(logging.Handler):

    LOG_LEVELS = {
        logging.CRITICAL:   "CRITICAL",
        logging.ERROR:      "ERROR",
        logging.WARNING:    "WARNING",
        logging.INFO:       "INFO",
        logging.DEBUG:      "DEBUG"
    }

    def __init__(self):
        super(TraceRobotPythonLogger, self).__init__()

    def handle(self, record):
        tracerobot.log_message(record.getMessage(), level=record.levelname)

class TraceRobotPlugin:
    def __init__(self, config):

        self.config = config
        self._stack = []
        self._logger = TraceRobotPythonLogger()

    @property
    def current_path(self):
        return [path for path, _ in self._stack]

    def _start_suite(self, name):
        # TODO: How to get meaningful suite docstring/metadata/source?
        suite = tracerobot.start_suite(name)
        self._stack.append((name, suite))

    def _end_suite(self):
        _, suite = self._stack.pop(-1)
        tracerobot.end_suite(suite)

    def _get_error_msg(self, call):
        if call and call.excinfo:
            stack_summary = traceback.extract_tb(call.excinfo.tb)
            frames = traceback.format_list(stack_summary)
            msg = frames[-1] + "\n" + call.excinfo.exconly()
            return msg

        else:
            return None

    def _is_test_started(self, item):
        try:
            return item.rt_test_info is not None
        except AttributeError:
            return False

    def _is_test_with_setup_and_teardown(self, item):
        try:
            return item.rt_test_with_setup_and_teardown
        except AttributeError:
            return False

    def _get_test_error_msg(self, item):
        """ Return earlier error message(s) from setup / test body phases. """
        msg1 = None
        msg2 = None
        try:
            if item.rt_test_error_msg:
                msg1 = item.rt_test_error_msg
        except AttributeError:
            return None

        try:
            if item.rt_test_teardown_error_msg:
                msg2 = "Error in Teardown: " + item.rt_test_teardown_error_msg
        except AttributeError:
            return None

        if msg1 and msg2:
            return msg1 + " " + msg2
        elif msg1:
            return msg1
        elif msg2:
            return msg2
        else:
            return None

    def _has_test_setup(self, item):
        try:
            return item.rt_test_setup_info is not None
        except AttributeError:
            return False

    def _has_test_body(self, item):
        try:
            return item.rt_test_body_info is not None
        except AttributeError:
            return False

    def _has_test_teardown(self, item):
        try:
            return item.rt_test_teardown_info is not None
        except AttributeError:
            return False

    def _start_test_envelope(self, item, with_setup_and_teardown=False):
        """ test envelope consists of
                [setup keyword] + test function keyword + [teardown keywords]
                """
        if self._is_test_started(item):
            return

        markers = [marker.name for marker in item.iter_markers()]

        item.rt_test_info = tracerobot.start_test(
            name=item.name,
            doc=item.function.__doc__,
            tags=markers)
        item.rt_test_with_setup_and_teardown = with_setup_and_teardown

        tracerobot.start_auto_trace()

    def _start_test_setup(self, item, fixturedef):
        assert self._is_test_with_setup_and_teardown

        if self._has_test_setup(item):
            self._finish_test_setup(item)

        # Applies to next keyword function called, returns automatically to "kw"
        tracerobot.set_auto_trace_kwtype('setup')

    def _finish_test_setup(self, item, call=None):
        if self._has_test_setup(item):
            error_msg = self._get_error_msg(call)
            item.rt_test_error_msg = error_msg
            item.rt_test_setup_info = None

    def _start_test_body(self, item):
        assert self._is_test_with_setup_and_teardown

    def _finish_test_body(self, item, call=None):

        error_msg = self._get_error_msg(call)
        item.rt_test_error_msg = error_msg

    def _start_test_teardown(self, item):
        assert self._is_test_with_setup_and_teardown
        tracerobot.set_auto_trace_kwtype('teardown')
        item.rt_test_teardown_info = tracerobot.start_keyword(
            "fixture(s)", "teardown")

    def _finish_test_teardown(self, item, call=None):
        if self._has_test_teardown(item):
            error_msg = self._get_error_msg(call)
            tracerobot.end_keyword(item.rt_test_teardown_info, error_msg=error_msg)
            item.rt_test_teardown_error_msg = error_msg
            item.rt_test_teardown_info = None

    def _finish_test_envelope(self, item, call=None):
        tracerobot.stop_auto_trace()

        if self._is_test_started(item):
            if call.excinfo:
                error_msg = self._get_error_msg(call)
            else:
                error_msg = self._get_test_error_msg(item)

            tracerobot.end_test(item.rt_test_info, error_msg)
            item.rt_test_info = None


    # Initialization hooks

    def pytest_sessionstart(self, session):
        # note: this becomes after the root-level suite has been created
        tracerobot_config = {}
        for var in ["robot_output", "autotrace_privates", "autotrace_libpaths"]:
            tracerobot_config[var] = self.config.getoption(var)

        # add _pytest module to list of silenced paths in order to avoid
        # logging of asserts related helper methods
        tracerobot_config['autotrace_silentpaths'] = _pytest.__path__
        tracerobot.tracerobot_init(tracerobot_config)

        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger().addHandler(self._logger)


    def pytest_sessionfinish(self, session, exitstatus):
        while self._stack:
            self._end_suite()

        tracerobot.close()

    # Test running hooks

    def pytest_runtest_logstart(self, nodeid, location):
        """Each directory and test file maps to a Robot Framework suite.
        Because pytest doesn't seem to provide hook for entering/leaving
        suites as such, the current suite must be determined before each test.
        """
        #filename, linenum, testname = location
        filename, _, _ = location

        target = filename.split(os.sep)
        common = common_items(self.current_path, target)

        while len(self.current_path) > len(common):
            self._end_suite()

        assert self.current_path == common

        while len(self.current_path) < len(target):
            name = target[len(self.current_path)]
            self._start_suite(name)

        assert self.current_path == target

    # Reporting hooks

    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(self, fixturedef, request):

        scope = fixturedef.scope    # 'function', 'class', 'module', 'session'

        if HOOK_DEBUG:
            # Note: run pytest with -s to see these
            print("\npytest_fixture_setup", fixturedef, request, request.node)

        if scope == 'function':
            # Function-scope fixtures can be starting a new test case
            item = request.node

            if not self._is_test_started(item):
                self._start_test_envelope(
                    item, with_setup_and_teardown=True)
                self._start_test_setup(item, fixturedef)

        fixture = tracerobot.start_keyword(
            name=fixturedef.argname,
            type="setup"
        )

        outcome = yield

        result = outcome.get_result()
        tracerobot.end_keyword(fixture, result)


    #def pytest_fixture_setup(self, fixturedef, request):
    #    return pytest_fixture_setup_wrap(self, fixturedef, request)

    def pytest_runtest_call(self, item):
        pass

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(self, item, nextitem):
        # TODO: Figure out how to wrap around individual fixture teardowns
        # All fixture teardowns run during yield (if they exist)

        # Might have to re-implement pytest_runtest_teardown from _pytest.runner
        # or do some ugly monkeypatching of the Session, like this:
        #
        # def monkey_finalizer(self, colitem):
        #     ... call finalizers and wrap them here ...
        #
        # import types
        # state = item.session._setupstate
        # state._callfinalizers = types.MethodType(monkey_finalizer, state)
        #
        yield

    def pytest_runtest_makereport(self, item, call):

        #call.when: (post)"setup", (post)"call", (post)"teardown"
        #note: setup and teardown are called even if a test has no fixture

        if HOOK_DEBUG:
            print("\npytest_runtest_makereport", item, call)

        if call.when == "setup":
            #  finish setup phase (if any), start test body

            if self._is_test_with_setup_and_teardown(item):
                self._finish_test_setup(item, call)
                if not call.excinfo:
                    self._start_test_body(item)
                else:
                    self._finish_test_envelope(item, call)
            else:
                self._start_test_envelope(item)

        # pytest_runtest_call(item) gets called between "setup" and "call"

        elif call.when == "call":
            # test body called, enter teardown phase
            if self._is_test_with_setup_and_teardown(item):
                self._finish_test_body(item, call)
                self._start_test_teardown(item)
            else:
                self._finish_test_envelope(item, call)

        elif call.when == "teardown":
            # teardown finished
            if self._is_test_with_setup_and_teardown(item):
                self._finish_test_teardown(item, call)
                self._finish_test_envelope(item, call)


    def pytest_assertion_pass(self, item, lineno, orig, expl):

        if HOOK_DEBUG:
            print("\npytest_assertion_pass", item.fspath, lineno, orig)

        path = item.fspath
        fname = os.path.basename(path)
        name = fname + ":" + str(lineno) + ": assert"
        assert_kw = tracerobot.start_keyword(name, args=[orig])
        tracerobot.log_message(expl)
        tracerobot.end_keyword(assert_kw)


def pytest_addoption(parser):
    group = parser.getgroup('tracerobot')
    group.addoption(
        '--robot-output',
        default='output.xml',
        help='Path to Robot Framework XML output'
    )
    group.addoption(
        '--autotrace-privates',
        default=False,
        action='store_const',
        const=True,
        help='If set, also auto trace private method.'
    )
    group.addoption(
        '--autotrace-libpaths',
        nargs="*",
        help='List of paths for which the autotracer is enabled.'
    )

    # TODO: should auto-tracing be configurable on/off?

def pytest_configure(config):
    plugin = TraceRobotPlugin(config)
    config.pluginmanager.register(plugin)
